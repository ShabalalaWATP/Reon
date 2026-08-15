"""Package authorisation and cross-package planning invariants."""

from __future__ import annotations

from uuid import UUID

from mist_service.board_models import BoardColumn, WorkPackageStatus
from mist_service.board_policy import authorise_board_manager, require
from mist_service.board_ports import BoardRepositoryPort, WorkPackageRecord
from mist_service.domain import Actor
from mist_service.errors import (
    BoardItemNotFound,
    InvalidBoardChange,
    TeamWorkspaceNotFound,
)
from mist_service.models import UserRole
from mist_service.request_identity_policy import require_requester_excluded
from mist_service.schemas.board import WorkPackageCommand

PACKAGE_STATUS_TO_COLUMN = {
    WorkPackageStatus.BACKLOG: BoardColumn.BACKLOG,
    WorkPackageStatus.READY: BoardColumn.READY,
    WorkPackageStatus.IN_PROGRESS: BoardColumn.IN_PROGRESS,
    WorkPackageStatus.BLOCKED: BoardColumn.BLOCKED,
    WorkPackageStatus.DONE: BoardColumn.COMPLETED,
    WorkPackageStatus.CANCELLED: BoardColumn.CANCELLED,
}


class BoardPackagePolicy:
    def __init__(self, board: BoardRepositoryPort) -> None:
        self._board = board

    async def authorise_create(
        self, actor: Actor, team_id: UUID, command: WorkPackageCommand
    ) -> None:
        members = await self._board.current_member_ids(team_id)
        require(actor.id in members, TeamWorkspaceNotFound())
        if actor.role is UserRole.DELIVERY_TEAM_LEAD:
            if command.grant_id is None:
                raise TeamWorkspaceNotFound()
            await authorise_board_manager(self._board, actor, team_id, command.grant_id)
            return
        require(
            actor.role is UserRole.DELIVERY_SPECIALIST
            and command.owner_user_id == actor.id,
            TeamWorkspaceNotFound(),
        )

    async def validate_links(
        self, actor: Actor, team_id: UUID, command: WorkPackageCommand
    ) -> None:
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
            await self._validate_request_link(actor, team_id, command)
        if command.iteration_id:
            require(
                await self._board.iteration_in_team(team_id, command.iteration_id),
                BoardItemNotFound(),
            )

    async def enforce_wip(
        self,
        team_id: UUID,
        package: WorkPackageRecord,
        target: WorkPackageStatus,
    ) -> None:
        target_column = PACKAGE_STATUS_TO_COLUMN.get(target)
        if target_column is None:
            return
        await self._board.lock_planning_aggregate(team_id)
        config = await self._board.configuration(team_id)
        limit = config.wip_limits.get(target_column.value) if config else None
        if limit is None:
            return
        count = await self._board.column_count(
            team_id,
            target_column,
            exclude_package_id=package.id,
        )
        require(count < limit, InvalidBoardChange("The team WIP limit is reached."))

    async def _validate_request_link(
        self, actor: Actor, team_id: UUID, command: WorkPackageCommand
    ) -> None:
        request_id = command.linked_request_id
        if request_id is None:
            return
        require(
            await self._board.request_belongs_to_team(team_id, request_id),
            BoardItemNotFound(),
        )
        requester_id = await self._board.request_requester_id(request_id)
        require_requester_excluded(
            requester_id,
            {actor.id, command.owner_user_id, *command.contributor_ids},
            BoardItemNotFound(),
        )
