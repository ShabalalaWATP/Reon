"""Exact-team workflow-board and work-package use cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from istari_service.board_models import BoardColumn, WorkPackage, WorkPackageStatus
from istari_service.board_policy import (
    authorise_board_manager,
    authorise_package_change,
    require,
)
from istari_service.board_projection import PACKAGE_TRANSITIONS, apply_filters, paginate
from istari_service.domain import Actor
from istari_service.errors import (
    BoardItemNotFound,
    InvalidBoardChange,
    TeamWorkspaceNotFound,
)
from istari_service.models import UserRole
from istari_service.repositories.board import SqlAlchemyBoardRepository
from istari_service.repositories.board_commands import SqlAlchemyBoardCommandRepository
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.schemas.board import (
    BoardConfigurationCommand,
    BoardConfigurationResult,
    BoardFilters,
    BoardItemType,
    BoardMoveAttempt,
    BoardResult,
    DeleteSavedViewCommand,
    SavedBoardViewCommand,
    SavedBoardViewResult,
    SavedBoardViewUpdate,
    WorkPackageCommand,
    WorkPackageList,
    WorkPackageMove,
    WorkPackageResult,
    WorkPackageUpdate,
    normalise_filters,
)

COLUMN_TO_PACKAGE_STATUS = {
    BoardColumn.BACKLOG: WorkPackageStatus.BACKLOG,
    BoardColumn.READY: WorkPackageStatus.READY,
    BoardColumn.IN_PROGRESS: WorkPackageStatus.IN_PROGRESS,
    BoardColumn.BLOCKED: WorkPackageStatus.BLOCKED,
    BoardColumn.COMPLETED: WorkPackageStatus.DONE,
    BoardColumn.CANCELLED: WorkPackageStatus.CANCELLED,
}
PACKAGE_STATUS_TO_COLUMN = {
    value: key for key, value in COLUMN_TO_PACKAGE_STATUS.items()
}


class BoardService:
    def __init__(
        self,
        board: SqlAlchemyBoardRepository,
        workspaces: SqlAlchemyTeamWorkspaceRepository,
    ) -> None:
        self._board = board
        self._commands = SqlAlchemyBoardCommandRepository(board)
        self._workspaces = workspaces

    async def board(
        self,
        actor: Actor,
        team_id: UUID,
        filters: BoardFilters,
        cursor: str | None,
        limit: int,
    ) -> BoardResult:
        await self._workspaces.require_read(actor.id, team_id)
        try:
            items, next_cursor = paginate(
                apply_filters(await self._board.projected_items(team_id), filters),
                cursor,
                limit,
            )
        except (ValueError, UnicodeError) as error:
            raise InvalidBoardChange("The board cursor is invalid.") from error
        config = await self._board.configuration(team_id)
        return BoardResult(
            items=items,
            next_cursor=next_cursor,
            wip_limits=config.wip_limits if config else {},
            configuration_version=config.version if config else 0,
            saved_views=await self._board.saved_views(team_id, actor.id),
            generated_at=datetime.now(UTC),
        )

    async def packages(
        self, actor: Actor, team_id: UUID, limit: int
    ) -> WorkPackageList:
        await self._workspaces.require_read(actor.id, team_id)
        return WorkPackageList(items=await self._board.list_packages(team_id, limit))

    async def package(
        self, actor: Actor, team_id: UUID, package_id: UUID
    ) -> WorkPackageResult:
        await self._workspaces.require_read(actor.id, team_id)
        return await self._board.package(team_id, package_id)

    async def create_package(
        self, actor: Actor, team_id: UUID, command: WorkPackageCommand
    ) -> WorkPackageResult:
        await self._authorise_create(actor, team_id, command)
        await self._validate_links(team_id, command)
        package = await self._commands.create_package(actor.id, team_id, command)
        if await self._commands.dependency_cycle(
            team_id, package.id, set(command.dependency_ids)
        ):
            raise InvalidBoardChange("Package dependencies cannot contain a cycle.")
        return await self._board.package(team_id, package.id)

    async def update_package(
        self,
        actor: Actor,
        team_id: UUID,
        package_id: UUID,
        command: WorkPackageUpdate,
    ) -> WorkPackageResult:
        package = await self._board.locked_package(
            team_id, package_id, command.expected_version
        )
        await authorise_package_change(self._board, actor, package, command.grant_id)
        require(
            actor.role is not UserRole.DELIVERY_SPECIALIST
            or command.owner_user_id == package.owner_user_id,
            BoardItemNotFound(),
        )
        await self._validate_links(team_id, command)
        if (
            package.id in command.dependency_ids
            or await self._commands.dependency_cycle(
                team_id, package.id, set(command.dependency_ids)
            )
        ):
            raise InvalidBoardChange("Package dependencies cannot contain a cycle.")
        await self._commands.replace_package(package, actor.id, command)
        return await self._board.package(team_id, package.id)

    async def move_package(
        self,
        actor: Actor,
        team_id: UUID,
        package_id: UUID,
        command: WorkPackageMove,
    ) -> WorkPackageResult:
        package = await self._board.locked_package(
            team_id, package_id, command.expected_version
        )
        await authorise_package_change(self._board, actor, package, command.grant_id)
        require(
            command.target in PACKAGE_TRANSITIONS[package.status],
            InvalidBoardChange("That package transition is not available."),
        )
        await self._enforce_wip(team_id, package, command.target)
        await self._commands.move_package(
            package, actor.id, command.target, command.reason
        )
        return await self._board.package(team_id, package.id)

    async def move_board_item(
        self, actor: Actor, team_id: UUID, command: BoardMoveAttempt
    ) -> WorkPackageResult:
        require(
            command.item_type is BoardItemType.WORK_PACKAGE,
            InvalidBoardChange(
                "Service-request movement must use its named workflow action."
            ),
        )
        target = COLUMN_TO_PACKAGE_STATUS.get(command.target)
        if target is None:
            raise InvalidBoardChange("That board move is unavailable.")
        return await self.move_package(
            actor,
            team_id,
            command.item_id,
            WorkPackageMove(
                grant_id=command.grant_id,
                expected_version=command.expected_version,
                target=target,
                reason=command.reason,
            ),
        )

    async def configure(
        self, actor: Actor, team_id: UUID, command: BoardConfigurationCommand
    ) -> BoardConfigurationResult:
        await authorise_board_manager(self._board, actor, team_id, command.grant_id)
        config = await self._commands.set_configuration(team_id, command)
        return BoardConfigurationResult(
            wip_limits=config.wip_limits, version=config.version
        )

    async def create_saved_view(
        self, actor: Actor, team_id: UUID, command: SavedBoardViewCommand
    ) -> SavedBoardViewResult:
        await self._workspaces.require_read(actor.id, team_id)
        view = await self._commands.create_saved_view(actor.id, team_id, command)
        return _saved_view(view.id, view.name, view.filters, view.version)

    async def update_saved_view(
        self,
        actor: Actor,
        team_id: UUID,
        view_id: UUID,
        command: SavedBoardViewUpdate,
    ) -> SavedBoardViewResult:
        await self._workspaces.require_read(actor.id, team_id)
        view = await self._commands.update_saved_view(
            actor.id, team_id, view_id, command
        )
        return _saved_view(view.id, view.name, view.filters, view.version)

    async def delete_saved_view(
        self,
        actor: Actor,
        team_id: UUID,
        view_id: UUID,
        command: DeleteSavedViewCommand,
    ) -> None:
        await self._workspaces.require_read(actor.id, team_id)
        await self._commands.delete_saved_view(
            actor.id, team_id, view_id, command.expected_version
        )

    async def _authorise_create(
        self, actor: Actor, team_id: UUID, command: WorkPackageCommand
    ) -> None:
        members = await self._board.current_member_ids(team_id)
        require(actor.id in members, TeamWorkspaceNotFound())
        if actor.role is UserRole.DELIVERY_TEAM_LEAD:
            if command.grant_id is None:
                raise TeamWorkspaceNotFound()
            await authorise_board_manager(self._board, actor, team_id, command.grant_id)
        else:
            require(
                actor.role is UserRole.DELIVERY_SPECIALIST
                and command.owner_user_id == actor.id,
                TeamWorkspaceNotFound(),
            )

    async def _validate_links(self, team_id: UUID, command: WorkPackageCommand) -> None:
        members = await self._board.current_member_ids(team_id)
        require(
            {command.owner_user_id, *command.contributor_ids} <= members,
            BoardItemNotFound(),
        )
        dependencies = set(command.dependency_ids)
        require(
            await self._board.package_ids_in_team(team_id, dependencies)
            == dependencies,
            BoardItemNotFound(),
        )
        if command.linked_request_id:
            require(
                await self._board.request_belongs_to_team(
                    team_id, command.linked_request_id
                ),
                BoardItemNotFound(),
            )
        if command.iteration_id:
            require(
                await self._board.iteration_in_team(team_id, command.iteration_id),
                BoardItemNotFound(),
            )

    async def _enforce_wip(
        self, team_id: UUID, package: WorkPackage, target: WorkPackageStatus
    ) -> None:
        target_column = PACKAGE_STATUS_TO_COLUMN.get(target)
        if target_column is None:
            return
        config = await self._board.configuration(team_id)
        limit = config.wip_limits.get(target_column.value) if config else None
        if limit is None:
            return
        count = sum(
            item.item.column is target_column and item.item.id != package.id
            for item in await self._board.projected_items(team_id)
        )
        require(count < limit, InvalidBoardChange("The team WIP limit is reached."))


def _saved_view(
    view_id: UUID, name: str, filters: dict[str, object], version: int
) -> SavedBoardViewResult:
    return SavedBoardViewResult(
        id=view_id, name=name, filters=normalise_filters(filters), version=version
    )
