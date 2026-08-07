"""Exact-team board reads and work-package aggregate projections."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.analytics_models import RequestAnalyticsFact
from istari_service.board_models import (
    CapacityReservation,
    ReservationStatus,
    SavedBoardView,
    TeamBoardConfiguration,
    TeamIteration,
    WorkPackage,
    WorkPackageContributor,
)
from istari_service.board_projection import (
    ProjectedBoardItem,
    package_projection,
    request_projection,
)
from istari_service.errors import BoardItemNotFound, StaleVersion
from istari_service.models import RequestStatus, ServiceRequest, User
from istari_service.organisation_models import UserOrganisationMembership
from istari_service.repositories.board_package_reads import (
    SqlAlchemyPackageReadRepository,
)
from istari_service.schemas.board import (
    IterationResult,
    SavedBoardViewResult,
    WorkPackageResult,
    normalise_filters,
)

BOARD_ROW_LIMIT = 500


class SqlAlchemyBoardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._package_reads = SqlAlchemyPackageReadRepository(session)

    async def projected_items(self, team_id: UUID) -> list[ProjectedBoardItem]:
        completed_cutoff = datetime.now(UTC) - timedelta(days=30)
        request_rows = (
            await self.session.execute(
                select(ServiceRequest, User.display_name)
                .join(
                    RequestAnalyticsFact,
                    RequestAnalyticsFact.request_id == ServiceRequest.id,
                )
                .outerjoin(User, User.id == ServiceRequest.assigned_specialist_id)
                .where(
                    RequestAnalyticsFact.team_unit_id == team_id,
                    or_(
                        ServiceRequest.status.not_in(
                            {
                                RequestStatus.COMPLETED,
                                RequestStatus.CLOSED_NOT_PROGRESSED,
                                RequestStatus.CANCELLED,
                            }
                        ),
                        ServiceRequest.updated_at >= completed_cutoff,
                    ),
                )
                .limit(BOARD_ROW_LIMIT)
            )
        ).all()
        package_rows = (
            await self.session.execute(
                select(WorkPackage, User.display_name)
                .join(User, User.id == WorkPackage.owner_user_id)
                .where(WorkPackage.team_id == team_id)
                .limit(BOARD_ROW_LIMIT)
            )
        ).all()
        requests = [request_projection(row[0], row[1]) for row in request_rows]
        packages = [package_projection(row[0], row[1]) for row in package_rows]
        return [item for item in requests if item is not None] + packages

    async def configuration(self, team_id: UUID) -> TeamBoardConfiguration | None:
        return await self.session.get(TeamBoardConfiguration, team_id)

    async def saved_views(
        self, team_id: UUID, owner_id: UUID
    ) -> list[SavedBoardViewResult]:
        rows = list(
            await self.session.scalars(
                select(SavedBoardView)
                .where(
                    SavedBoardView.team_id == team_id,
                    SavedBoardView.owner_user_id == owner_id,
                )
                .order_by(SavedBoardView.name, SavedBoardView.id)
            )
        )
        return [
            SavedBoardViewResult(
                id=item.id,
                name=item.name,
                filters=normalise_filters(item.filters),
                version=item.version,
            )
            for item in rows
        ]

    async def list_packages(self, team_id: UUID, limit: int) -> list[WorkPackageResult]:
        return await self._package_reads.list_packages(team_id, limit)

    async def package(self, team_id: UUID, package_id: UUID) -> WorkPackageResult:
        return await self._package_reads.get(team_id, package_id)

    async def locked_package(
        self, team_id: UUID, package_id: UUID, expected_version: int
    ) -> WorkPackage:
        package = await self.session.scalar(
            select(WorkPackage)
            .where(WorkPackage.id == package_id, WorkPackage.team_id == team_id)
            .with_for_update()
        )
        if package is None:
            raise BoardItemNotFound()
        if package.version != expected_version:
            raise StaleVersion()
        return package

    async def current_member_ids(self, team_id: UUID) -> set[UUID]:
        return set(
            await self.session.scalars(
                select(UserOrganisationMembership.user_id)
                .join(User, User.id == UserOrganisationMembership.user_id)
                .where(
                    UserOrganisationMembership.unit_id == team_id,
                    User.is_active.is_(True),
                )
            )
        )

    async def is_contributor(self, package_id: UUID, user_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(WorkPackageContributor.user_id).where(
                    WorkPackageContributor.package_id == package_id,
                    WorkPackageContributor.user_id == user_id,
                )
            )
            is not None
        )

    async def request_belongs_to_team(self, team_id: UUID, request_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(RequestAnalyticsFact.request_id).where(
                    RequestAnalyticsFact.request_id == request_id,
                    RequestAnalyticsFact.team_unit_id == team_id,
                )
            )
            is not None
        )

    async def package_ids_in_team(
        self, team_id: UUID, package_ids: set[UUID]
    ) -> set[UUID]:
        if not package_ids:
            return set()
        return set(
            await self.session.scalars(
                select(WorkPackage.id).where(
                    WorkPackage.team_id == team_id,
                    WorkPackage.id.in_(package_ids),
                )
            )
        )

    async def iteration_in_team(self, team_id: UUID, iteration_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(TeamIteration.id).where(
                    TeamIteration.id == iteration_id,
                    TeamIteration.team_id == team_id,
                )
            )
            is not None
        )

    async def active_reservations(
        self, team_id: UUID, start: datetime, end: datetime
    ) -> list[CapacityReservation]:
        return list(
            await self.session.scalars(
                select(CapacityReservation).where(
                    CapacityReservation.team_id == team_id,
                    CapacityReservation.status == ReservationStatus.ACTIVE,
                    CapacityReservation.starts_at < end,
                    CapacityReservation.ends_at > start,
                )
            )
        )

    async def iterations(self, team_id: UUID) -> list[IterationResult]:
        rows = list(
            await self.session.scalars(
                select(TeamIteration)
                .where(TeamIteration.team_id == team_id)
                .order_by(TeamIteration.starts_on.desc(), TeamIteration.id)
                .limit(100)
            )
        )
        return [
            IterationResult(
                id=item.id,
                name=item.name,
                goal=item.goal,
                starts_on=item.starts_on,
                ends_on=item.ends_on,
                status=item.status,
                completion_summary=item.completion_summary,
                version=item.version,
            )
            for item in rows
        ]
