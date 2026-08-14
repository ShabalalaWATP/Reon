"""Exact-team workflow-board and work-package use cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from istari_service.board_models import BoardColumn, WorkPackageStatus
from istari_service.board_policy import (
    authorise_board_manager,
    authorise_package_change,
    require,
)
from istari_service.board_ports import BoardCommandPort, BoardRepositoryPort
from istari_service.board_projection import PACKAGE_TRANSITIONS
from istari_service.domain import Actor
from istari_service.errors import (
    BoardItemNotFound,
    InvalidBoardChange,
    TeamWorkspaceNotFound,
)
from istari_service.identity_context import require_staff_context
from istari_service.models import UserRole
from istari_service.schemas.board import (
    BoardConfigurationCommand,
    BoardConfigurationResult,
    BoardFilters,
    BoardItem,
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
from istari_service.services.board_package_policy import BoardPackagePolicy
from istari_service.services.board_request_conflict import (
    require_package_requester_excluded,
)
from istari_service.services.team_workspace_ports import TeamWorkspaceReadPort

COLUMN_TO_PACKAGE_STATUS = {
    BoardColumn.BACKLOG: WorkPackageStatus.BACKLOG,
    BoardColumn.READY: WorkPackageStatus.READY,
    BoardColumn.IN_PROGRESS: WorkPackageStatus.IN_PROGRESS,
    BoardColumn.BLOCKED: WorkPackageStatus.BLOCKED,
    BoardColumn.COMPLETED: WorkPackageStatus.DONE,
    BoardColumn.CANCELLED: WorkPackageStatus.CANCELLED,
}


class BoardService:
    def __init__(
        self,
        board: BoardRepositoryPort,
        commands: BoardCommandPort,
        workspaces: TeamWorkspaceReadPort,
    ) -> None:
        self._board = board
        self._commands = commands
        self._workspaces = workspaces
        self._package_policy = BoardPackagePolicy(board)

    async def board(
        self,
        actor: Actor,
        team_id: UUID,
        filters: BoardFilters,
        cursor: str | None,
        limit: int,
    ) -> BoardResult:
        self._require_staff(actor)
        await self._workspaces.require_read(actor.id, team_id)
        try:
            items, next_cursor = await self._board.board_page(
                team_id, filters, cursor, limit
            )
        except (ValueError, UnicodeError) as error:
            raise InvalidBoardChange("The board cursor is invalid.") from error
        column_counts = await self._board.board_column_counts(team_id, filters)
        config = await self._board.configuration(team_id)
        return BoardResult(
            items=items,
            next_cursor=next_cursor,
            column_counts=column_counts,
            total_count=sum(
                count
                for column, count in column_counts.items()
                if not filters.columns or column in filters.columns
            ),
            wip_limits=config.wip_limits if config else {},
            configuration_version=config.version if config else 0,
            saved_views=await self._board.saved_views(team_id, actor.id),
            generated_at=datetime.now(UTC),
        )

    async def board_request(
        self, actor: Actor, team_id: UUID, request_id: UUID
    ) -> BoardItem:
        self._require_staff(actor)
        await self._workspaces.require_read(actor.id, team_id)
        return await self._board.request_item(team_id, request_id)

    async def packages(
        self, actor: Actor, team_id: UUID, limit: int
    ) -> WorkPackageList:
        self._require_staff(actor)
        await self._workspaces.require_read(actor.id, team_id)
        return WorkPackageList(items=await self._board.list_packages(team_id, limit))

    async def package(
        self, actor: Actor, team_id: UUID, package_id: UUID
    ) -> WorkPackageResult:
        self._require_staff(actor)
        await self._workspaces.require_read(actor.id, team_id)
        return await self._board.package(team_id, package_id)

    async def create_package(
        self, actor: Actor, team_id: UUID, command: WorkPackageCommand
    ) -> WorkPackageResult:
        self._require_staff(actor)
        await self._package_policy.authorise_create(actor, team_id, command)
        await self._board.lock_planning_aggregate(team_id)
        await self._package_policy.validate_links(actor, team_id, command)
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
        self._require_staff(actor)
        package = await self._board.locked_package(
            team_id, package_id, command.expected_version
        )
        await authorise_package_change(self._board, actor, package, command.grant_id)
        await require_package_requester_excluded(self._board, package, actor.id)
        require(
            actor.role is not UserRole.DELIVERY_SPECIALIST
            or command.owner_user_id == package.owner_user_id,
            BoardItemNotFound(),
        )
        await self._board.lock_planning_aggregate(team_id)
        await self._package_policy.validate_links(actor, team_id, command)
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
        self._require_staff(actor)
        package = await self._board.locked_package(
            team_id, package_id, command.expected_version
        )
        await authorise_package_change(self._board, actor, package, command.grant_id)
        await require_package_requester_excluded(self._board, package, actor.id)
        require(
            command.target in PACKAGE_TRANSITIONS[package.status],
            InvalidBoardChange("That package transition is not available."),
        )
        await self._package_policy.enforce_wip(team_id, package, command.target)
        await self._commands.move_package(
            package, actor.id, command.target, command.reason
        )
        return await self._board.package(team_id, package.id)

    async def move_board_item(
        self, actor: Actor, team_id: UUID, command: BoardMoveAttempt
    ) -> WorkPackageResult:
        self._require_staff(actor)
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
        self._require_staff(actor)
        await authorise_board_manager(self._board, actor, team_id, command.grant_id)
        await self._board.lock_planning_aggregate(team_id)
        config = await self._commands.set_configuration(team_id, command)
        return BoardConfigurationResult(
            wip_limits=config.wip_limits, version=config.version
        )

    async def create_saved_view(
        self, actor: Actor, team_id: UUID, command: SavedBoardViewCommand
    ) -> SavedBoardViewResult:
        self._require_staff(actor)
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
        self._require_staff(actor)
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
        self._require_staff(actor)
        await self._workspaces.require_read(actor.id, team_id)
        await self._commands.delete_saved_view(
            actor.id, team_id, view_id, command.expected_version
        )

    @staticmethod
    def _require_staff(actor: Actor) -> None:
        require_staff_context(actor, TeamWorkspaceNotFound())


def _saved_view(
    view_id: UUID, name: str, filters: dict[str, object], version: int
) -> SavedBoardViewResult:
    return SavedBoardViewResult(
        id=view_id, name=name, filters=normalise_filters(filters), version=version
    )
