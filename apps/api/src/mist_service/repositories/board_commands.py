"""Transactional mutations for independent team planning aggregates."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select

from mist_service.board_models import (
    SavedBoardView,
    TeamBoardConfiguration,
    WorkPackage,
    WorkPackageActivity,
    WorkPackageActivityType,
    WorkPackageContributor,
    WorkPackageDependency,
    WorkPackageStatus,
)
from mist_service.errors import BoardItemNotFound, StaleVersion
from mist_service.repositories.board import SqlAlchemyBoardRepository
from mist_service.schemas.board import (
    BoardConfigurationCommand,
    SavedBoardViewCommand,
    SavedBoardViewUpdate,
    WorkPackageCommand,
)


class SqlAlchemyBoardCommandRepository:
    def __init__(self, board: SqlAlchemyBoardRepository) -> None:
        self.board = board
        self.session = board.session

    async def create_package(
        self, actor_id: UUID, team_id: UUID, command: WorkPackageCommand
    ) -> WorkPackage:
        package = WorkPackage(
            team_id=team_id,
            status=WorkPackageStatus.BACKLOG,
            created_by_user_id=actor_id,
            version=1,
            **_package_values(command),
        )
        self.session.add(package)
        await self.session.flush()
        await self._replace_links(package.id, command)
        self._activity(
            package,
            actor_id,
            WorkPackageActivityType.CREATED,
            "Work package created.",
        )
        return package

    async def replace_package(
        self, package: WorkPackage, actor_id: UUID, command: WorkPackageCommand
    ) -> WorkPackage:
        for field, value in _package_values(command).items():
            setattr(package, field, value)
        package.version += 1
        await self._replace_links(package.id, command)
        self._activity(
            package,
            actor_id,
            WorkPackageActivityType.UPDATED,
            "Work package planning detail updated.",
        )
        return package

    async def move_package(
        self,
        package: WorkPackage,
        actor_id: UUID,
        target: WorkPackageStatus,
        reason: str,
    ) -> WorkPackage:
        prior = package.status
        package.status = target
        package.version += 1
        self._activity(
            package,
            actor_id,
            WorkPackageActivityType.MOVED,
            f"Work package moved from {prior.value} to {target.value}.",
            {"from": prior.value, "to": target.value, "reason": reason.strip()},
        )
        return package

    async def dependency_cycle(
        self, team_id: UUID, package_id: UUID, proposed: set[UUID]
    ) -> bool:
        rows = (
            await self.session.execute(
                select(
                    WorkPackageDependency.package_id,
                    WorkPackageDependency.depends_on_id,
                )
                .join(WorkPackage, WorkPackage.id == WorkPackageDependency.package_id)
                .where(WorkPackage.team_id == team_id)
            )
        ).all()
        edges: dict[UUID, set[UUID]] = {}
        for source, target in rows:
            edges.setdefault(source, set()).add(target)
        edges[package_id] = proposed

        def reaches_current(start: UUID) -> bool:
            pending, seen = [start], set()
            while pending:
                current = pending.pop()
                if current == package_id:
                    return True
                if current not in seen:
                    seen.add(current)
                    pending.extend(edges.get(current, ()))
            return False

        return any(reaches_current(item) for item in proposed)

    async def set_configuration(
        self, team_id: UUID, command: BoardConfigurationCommand
    ) -> TeamBoardConfiguration:
        config = await self.session.get(
            TeamBoardConfiguration, team_id, with_for_update=True
        )
        if config is None:
            if command.expected_version != 0:
                raise StaleVersion()
            config = TeamBoardConfiguration(
                team_id=team_id,
                wip_limits={
                    key.value: value for key, value in command.wip_limits.items()
                },
                version=1,
            )
            self.session.add(config)
        else:
            if config.version != command.expected_version:
                raise StaleVersion()
            config.wip_limits = {
                key.value: value for key, value in command.wip_limits.items()
            }
            config.version += 1
        await self.session.flush()
        return config

    async def create_saved_view(
        self,
        actor_id: UUID,
        team_id: UUID,
        command: SavedBoardViewCommand,
    ) -> SavedBoardView:
        view = SavedBoardView(
            team_id=team_id,
            owner_user_id=actor_id,
            name=command.name.strip(),
            filters=command.filters.model_dump(mode="json"),
            version=1,
        )
        self.session.add(view)
        await self.session.flush()
        return view

    async def update_saved_view(
        self,
        actor_id: UUID,
        team_id: UUID,
        view_id: UUID,
        command: SavedBoardViewUpdate,
    ) -> SavedBoardView:
        view = await self._locked_view(actor_id, team_id, view_id)
        if view.version != command.expected_version:
            raise StaleVersion()
        view.name = command.name.strip()
        view.filters = command.filters.model_dump(mode="json")
        view.version += 1
        return view

    async def delete_saved_view(
        self, actor_id: UUID, team_id: UUID, view_id: UUID, expected_version: int
    ) -> None:
        view = await self._locked_view(actor_id, team_id, view_id)
        if view.version != expected_version:
            raise StaleVersion()
        await self.session.delete(view)

    async def _locked_view(
        self, actor_id: UUID, team_id: UUID, view_id: UUID
    ) -> SavedBoardView:
        view = await self.session.scalar(
            select(SavedBoardView)
            .where(
                SavedBoardView.id == view_id,
                SavedBoardView.owner_user_id == actor_id,
                SavedBoardView.team_id == team_id,
            )
            .with_for_update()
        )
        if view is None:
            raise BoardItemNotFound()
        return view

    async def _replace_links(
        self, package_id: UUID, command: WorkPackageCommand
    ) -> None:
        await self.session.execute(
            delete(WorkPackageContributor).where(
                WorkPackageContributor.package_id == package_id
            )
        )
        await self.session.execute(
            delete(WorkPackageDependency).where(
                WorkPackageDependency.package_id == package_id
            )
        )
        self.session.add_all(
            [
                WorkPackageContributor(package_id=package_id, user_id=user_id)
                for user_id in command.contributor_ids
            ]
            + [
                WorkPackageDependency(package_id=package_id, depends_on_id=item)
                for item in command.dependency_ids
            ]
        )

    def _activity(
        self,
        package: WorkPackage,
        actor_id: UUID,
        type_: WorkPackageActivityType,
        summary: str,
        details: dict[str, object] | None = None,
    ) -> None:
        self.session.add(
            WorkPackageActivity(
                package_id=package.id,
                team_id=package.team_id,
                actor_user_id=actor_id,
                type=type_,
                summary=summary,
                details=details or {},
            )
        )


def _package_values(command: WorkPackageCommand) -> dict[str, object]:
    return {
        "linked_request_id": command.linked_request_id,
        "iteration_id": command.iteration_id,
        "title": command.title.strip(),
        "description": command.description.strip(),
        "owner_user_id": command.owner_user_id,
        "estimate_points": command.estimate_points,
        "remaining_effort_minutes": command.remaining_effort_minutes,
        "due_on": command.due_on,
        "priority": command.priority,
        "blockers": command.blockers.strip(),
        "acceptance_criteria": command.acceptance_criteria.strip(),
    }
