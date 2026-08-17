"""Capacity reservations and optional time-boxed team iterations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from mist_service.board_policy import (
    authorise_board_manager,
    authorise_package_change,
    require,
)
from mist_service.board_ports import (
    BoardIterationAnalyticsPort,
    BoardPlanningCommandPort,
    BoardRepositoryPort,
    IterationRecord,
)
from mist_service.domain import Actor
from mist_service.errors import BoardItemNotFound, TeamWorkspaceNotFound
from mist_service.identity_context import require_staff_context
from mist_service.management_models import ManagementAction
from mist_service.schemas.board import (
    IterationCloseCommand,
    IterationCommand,
    IterationList,
    IterationResult,
    ReservationCancelCommand,
    ReservationCommand,
    WorkPackageResult,
)
from mist_service.services.board_request_conflict import (
    require_package_requester_excluded,
)
from mist_service.services.team_workspace_ports import TeamWorkspaceReadPort


class BoardPlanningService:
    def __init__(
        self,
        board: BoardRepositoryPort,
        commands: BoardPlanningCommandPort,
        workspaces: TeamWorkspaceReadPort,
        analytics: BoardIterationAnalyticsPort,
    ) -> None:
        self._board = board
        self._commands = commands
        self._workspaces = workspaces
        self._analytics = analytics

    async def reserve(
        self,
        actor: Actor,
        team_id: UUID,
        package_id: UUID,
        expected_version: int,
        command: ReservationCommand,
    ) -> WorkPackageResult:
        self._require_staff(actor)
        package = await self._board.locked_package(
            team_id, package_id, expected_version
        )
        await authorise_package_change(self._board, actor, package, command.grant_id)
        await require_package_requester_excluded(
            self._board, package, actor.id, [command.user_id]
        )
        members = await self._board.current_member_ids(team_id)
        require(command.user_id in members, BoardItemNotFound())
        await self._commands.create_reservation(package, actor.id, command)
        return await self._board.package(team_id, package.id)

    async def cancel_reservation(
        self,
        actor: Actor,
        team_id: UUID,
        package_id: UUID,
        reservation_id: UUID,
        package_version: int,
        command: ReservationCancelCommand,
    ) -> WorkPackageResult:
        self._require_staff(actor)
        package = await self._board.locked_package(team_id, package_id, package_version)
        await authorise_package_change(self._board, actor, package, command.grant_id)
        await require_package_requester_excluded(self._board, package, actor.id)
        await self._commands.cancel_reservation(
            package, reservation_id, actor.id, command
        )
        return await self._board.package(team_id, package.id)

    async def iterations(self, actor: Actor, team_id: UUID) -> IterationList:
        self._require_staff(actor)
        await self._workspaces.require_projection_read(
            actor.id, team_id, ManagementAction.BOARD
        )
        return IterationList(items=await self._board.iterations(team_id))

    async def create_iteration(
        self, actor: Actor, team_id: UUID, command: IterationCommand
    ) -> IterationResult:
        self._require_staff(actor)
        await authorise_board_manager(self._board, actor, team_id, command.grant_id)
        return _iteration(
            await self._commands.create_iteration(actor.id, team_id, command)
        )

    async def close_iteration(
        self,
        actor: Actor,
        team_id: UUID,
        iteration_id: UUID,
        command: IterationCloseCommand,
    ) -> IterationResult:
        self._require_staff(actor)
        await authorise_board_manager(self._board, actor, team_id, command.grant_id)
        closed_at = datetime.now(UTC)
        iteration = await self._commands.close_iteration(team_id, iteration_id, command)
        await self._analytics.project_closed_iteration(iteration, occurred_at=closed_at)
        return _iteration(iteration)

    @staticmethod
    def _require_staff(actor: Actor) -> None:
        require_staff_context(actor, TeamWorkspaceNotFound())


def _iteration(item: IterationRecord) -> IterationResult:
    return IterationResult(
        id=item.id,
        name=item.name,
        goal=item.goal,
        starts_on=item.starts_on,
        ends_on=item.ends_on,
        status=item.status,
        completion_summary=item.completion_summary,
        version=item.version,
    )
