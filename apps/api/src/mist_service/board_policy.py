"""Final-boundary exact-team authority for board and package mutations."""

from __future__ import annotations

from uuid import UUID

from mist_service.board_ports import (
    BoardPlanningReadPort,
    WorkPackageRecord,
)
from mist_service.domain import Actor
from mist_service.errors import BoardItemNotFound, TeamWorkspaceNotFound
from mist_service.management_models import ManagementAction
from mist_service.models import UserRole


async def authorise_board_manager(
    board: BoardPlanningReadPort,
    actor: Actor,
    team_id: UUID,
    grant_id: UUID,
) -> None:
    require(actor.role is UserRole.DELIVERY_TEAM_LEAD, TeamWorkspaceNotFound())
    authorised = await board.has_management_authority(
        actor_id=actor.id,
        grant_id=grant_id,
        team_id=team_id,
        action=ManagementAction.BOARD,
    )
    require(authorised, TeamWorkspaceNotFound())


async def authorise_package_change(
    board: BoardPlanningReadPort,
    actor: Actor,
    package: WorkPackageRecord,
    grant_id: UUID | None,
) -> None:
    if actor.role is UserRole.DELIVERY_TEAM_LEAD:
        if grant_id is None:
            raise TeamWorkspaceNotFound()
        await authorise_board_manager(board, actor, package.team_id, grant_id)
        return
    require(
        actor.role is UserRole.DELIVERY_SPECIALIST
        and (
            package.owner_user_id == actor.id
            or await board.is_contributor(package.id, actor.id)
        ),
        BoardItemNotFound(),
    )


def require(condition: bool, error: Exception) -> None:
    if condition:
        return
    raise error
