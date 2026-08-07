"""Bulk work-package read projections without per-row database round trips."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.board_models import (
    CapacityReservation,
    WorkPackage,
    WorkPackageActivity,
    WorkPackageContributor,
    WorkPackageDependency,
)
from istari_service.errors import BoardItemNotFound
from istari_service.models import User
from istari_service.schemas.board import (
    CapacityReservationResult,
    WorkPackageActivityResult,
    WorkPackageContributorResult,
    WorkPackageResult,
)


class SqlAlchemyPackageReadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_packages(self, team_id: UUID, limit: int) -> list[WorkPackageResult]:
        rows = (
            await self._session.execute(
                select(WorkPackage, User.display_name)
                .join(User, User.id == WorkPackage.owner_user_id)
                .where(WorkPackage.team_id == team_id)
                .order_by(WorkPackage.due_on, WorkPackage.id)
                .limit(limit)
            )
        ).all()
        return await self._results([(row[0], row[1]) for row in rows])

    async def get(self, team_id: UUID, package_id: UUID) -> WorkPackageResult:
        row = (
            await self._session.execute(
                select(WorkPackage, User.display_name)
                .join(User, User.id == WorkPackage.owner_user_id)
                .where(
                    WorkPackage.id == package_id,
                    WorkPackage.team_id == team_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise BoardItemNotFound()
        return (await self._results([(row[0], row[1])]))[0]

    async def _results(
        self, rows: list[tuple[WorkPackage, str]]
    ) -> list[WorkPackageResult]:
        package_ids = [item[0].id for item in rows]
        if not package_ids:
            return []
        contributors: dict[UUID, list[WorkPackageContributorResult]] = defaultdict(list)
        contributor_rows = (
            await self._session.execute(
                select(
                    WorkPackageContributor.package_id,
                    WorkPackageContributor.user_id,
                    User.display_name,
                )
                .join(User, User.id == WorkPackageContributor.user_id)
                .where(WorkPackageContributor.package_id.in_(package_ids))
                .order_by(User.display_name, User.id)
            )
        ).all()
        for package_id, user_id, display_name in contributor_rows:
            contributors[package_id].append(
                WorkPackageContributorResult(
                    user_id=user_id,
                    display_name=display_name,
                )
            )
        dependencies: dict[UUID, list[UUID]] = defaultdict(list)
        dependency_rows = (
            await self._session.execute(
                select(
                    WorkPackageDependency.package_id,
                    WorkPackageDependency.depends_on_id,
                ).where(WorkPackageDependency.package_id.in_(package_ids))
            )
        ).all()
        for package_id, dependency_id in dependency_rows:
            dependencies[package_id].append(dependency_id)
        activities: dict[UUID, list[WorkPackageActivityResult]] = defaultdict(list)
        activity_rows = (
            await self._session.execute(
                select(WorkPackageActivity, User.display_name)
                .join(User, User.id == WorkPackageActivity.actor_user_id)
                .where(WorkPackageActivity.package_id.in_(package_ids))
                .order_by(
                    WorkPackageActivity.package_id,
                    WorkPackageActivity.created_at.desc(),
                    WorkPackageActivity.id,
                )
                .limit(len(package_ids) * 200)
            )
        ).all()
        for item, display_name in activity_rows:
            if len(activities[item.package_id]) < 200:
                activities[item.package_id].append(
                    WorkPackageActivityResult(
                        id=item.id,
                        type=item.type,
                        summary=item.summary,
                        actor_display_name=display_name,
                        created_at=item.created_at,
                    )
                )
        reservations: dict[UUID, list[CapacityReservationResult]] = defaultdict(list)
        reservation_rows = (
            await self._session.execute(
                select(CapacityReservation, User.display_name)
                .join(User, User.id == CapacityReservation.user_id)
                .where(CapacityReservation.package_id.in_(package_ids))
                .order_by(
                    CapacityReservation.package_id,
                    CapacityReservation.starts_at,
                    CapacityReservation.id,
                )
                .limit(len(package_ids) * 200)
            )
        ).all()
        for item, display_name in reservation_rows:
            if len(reservations[item.package_id]) < 200:
                reservations[item.package_id].append(
                    CapacityReservationResult(
                        id=item.id,
                        user_id=item.user_id,
                        user_display_name=display_name,
                        starts_at=item.starts_at,
                        ends_at=item.ends_at,
                        minutes=item.minutes,
                        status=item.status,
                        reason=item.reason,
                        version=item.version,
                    )
                )
        return [
            WorkPackageResult(
                id=package.id,
                team_id=package.team_id,
                linked_request_id=package.linked_request_id,
                iteration_id=package.iteration_id,
                title=package.title,
                description=package.description,
                owner_user_id=package.owner_user_id,
                owner_display_name=owner_name,
                contributors=contributors[package.id],
                estimate_points=package.estimate_points,
                remaining_effort_minutes=package.remaining_effort_minutes,
                due_on=package.due_on,
                priority=package.priority,
                status=package.status,
                blockers=package.blockers,
                acceptance_criteria=package.acceptance_criteria,
                dependency_ids=dependencies[package.id],
                version=package.version,
                activities=activities[package.id],
                reservations=reservations[package.id],
            )
            for package, owner_name in rows
        ]
