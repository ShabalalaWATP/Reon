"""Exact-team board reads and work-package aggregate projections."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.analytics_models import RequestAnalyticsFact
from istari_service.board_models import (
    BoardColumn,
    SavedBoardView,
    TeamBoardConfiguration,
    TeamIteration,
    WorkPackage,
    WorkPackageContributor,
)
from istari_service.board_projection import ProjectedBoardItem, request_projection
from istari_service.errors import BoardItemNotFound, StaleVersion, TeamWorkspaceNotFound
from istari_service.models import ServiceRequest, User
from istari_service.organisation_models import OrganisationUnit
from istari_service.repositories.board_package_reads import (
    SqlAlchemyPackageReadRepository,
)
from istari_service.repositories.board_page import SqlAlchemyBoardPageRepository
from istari_service.schemas.board import (
    BoardFilters,
    BoardItem,
    IterationResult,
    SavedBoardViewResult,
    WorkPackageResult,
    normalise_filters,
)
from istari_service.team_models import TeamMembership

BOARD_ROW_LIMIT = 500


class SqlAlchemyBoardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._package_reads = SqlAlchemyPackageReadRepository(session)
        self._page_reads = SqlAlchemyBoardPageRepository(session)

    async def projected_items(self, team_id: UUID) -> list[ProjectedBoardItem]:
        return await self._page_reads.projected(
            team_id, BoardFilters(), None, BOARD_ROW_LIMIT
        )

    async def board_page(
        self,
        team_id: UUID,
        filters: BoardFilters,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[BoardItem], str | None]:
        return await self._page_reads.page(team_id, filters, cursor, limit)

    async def board_column_counts(
        self, team_id: UUID, filters: BoardFilters
    ) -> dict[BoardColumn, int]:
        return await self._page_reads.filtered_column_counts(team_id, filters)

    async def request_item(self, team_id: UUID, request_id: UUID) -> BoardItem:
        row = (
            await self.session.execute(
                select(ServiceRequest, User.display_name)
                .outerjoin(User, User.id == ServiceRequest.assigned_specialist_id)
                .where(
                    ServiceRequest.id == request_id,
                    ServiceRequest.assigned_delivery_team_id == team_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise BoardItemNotFound()
        request, owner_name = row
        projected = request_projection(request, owner_name)
        if projected is None:
            raise BoardItemNotFound()
        return projected.item

    async def column_count(
        self,
        team_id: UUID,
        column: BoardColumn,
        *,
        exclude_package_id: UUID,
    ) -> int:
        return await self._page_reads.column_count(
            team_id, column, exclude_package_id=exclude_package_id
        )

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

    async def lock_planning_aggregate(self, team_id: UUID) -> None:
        """Serialise invariants which span multiple packages in one team."""

        locked_team_id = await self.session.scalar(
            select(OrganisationUnit.id)
            .where(OrganisationUnit.id == team_id)
            .with_for_update()
        )
        if locked_team_id is None:
            raise TeamWorkspaceNotFound()

    async def current_member_ids(self, team_id: UUID) -> set[UUID]:
        now = datetime.now(UTC)
        return set(
            await self.session.scalars(
                select(TeamMembership.user_id)
                .join(User, User.id == TeamMembership.user_id)
                .where(
                    TeamMembership.team_id == team_id,
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > now,
                    ),
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
