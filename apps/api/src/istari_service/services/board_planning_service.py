"""Capacity reservations and optional time-boxed team iterations."""

from __future__ import annotations

from uuid import UUID

from istari_service.board_models import TeamIteration
from istari_service.board_policy import (
    authorise_board_manager,
    authorise_package_change,
    require,
)
from istari_service.domain import Actor
from istari_service.errors import BoardItemNotFound
from istari_service.repositories.board import SqlAlchemyBoardRepository
from istari_service.repositories.board_planning_commands import (
    SqlAlchemyBoardPlanningCommandRepository,
)
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.schemas.board import (
    IterationCloseCommand,
    IterationCommand,
    IterationList,
    IterationResult,
    ReservationCancelCommand,
    ReservationCommand,
    WorkPackageResult,
)


class BoardPlanningService:
    def __init__(
        self,
        board: SqlAlchemyBoardRepository,
        workspaces: SqlAlchemyTeamWorkspaceRepository,
    ) -> None:
        self._board = board
        self._commands = SqlAlchemyBoardPlanningCommandRepository(board)
        self._workspaces = workspaces

    async def reserve(
        self,
        actor: Actor,
        team_id: UUID,
        package_id: UUID,
        expected_version: int,
        command: ReservationCommand,
    ) -> WorkPackageResult:
        package = await self._board.locked_package(
            team_id, package_id, expected_version
        )
        await authorise_package_change(self._board, actor, package, command.grant_id)
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
        package = await self._board.locked_package(team_id, package_id, package_version)
        await authorise_package_change(self._board, actor, package, command.grant_id)
        await self._commands.cancel_reservation(
            package, reservation_id, actor.id, command
        )
        return await self._board.package(team_id, package.id)

    async def iterations(self, actor: Actor, team_id: UUID) -> IterationList:
        await self._workspaces.require_read(actor.id, team_id)
        return IterationList(items=await self._board.iterations(team_id))

    async def create_iteration(
        self, actor: Actor, team_id: UUID, command: IterationCommand
    ) -> IterationResult:
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
        await authorise_board_manager(self._board, actor, team_id, command.grant_id)
        return _iteration(
            await self._commands.close_iteration(team_id, iteration_id, command)
        )


def _iteration(item: TeamIteration) -> IterationResult:
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
