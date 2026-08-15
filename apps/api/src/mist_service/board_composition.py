"""Compose board use cases with request-scoped persistence adapters."""

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.board_ports import (
    BoardCommandPort,
    BoardIterationAnalyticsPort,
    BoardPlanningCommandPort,
    BoardRepositoryPort,
)
from mist_service.repositories.board import SqlAlchemyBoardRepository
from mist_service.repositories.board_analytics import (
    SqlAlchemyBoardIterationAnalytics,
)
from mist_service.repositories.board_commands import SqlAlchemyBoardCommandRepository
from mist_service.repositories.board_planning_commands import (
    SqlAlchemyBoardPlanningCommandRepository,
)
from mist_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from mist_service.services.board_planning_service import BoardPlanningService
from mist_service.services.board_service import BoardService
from mist_service.services.team_workspace_ports import TeamWorkspaceReadPort


def board_services(
    session: AsyncSession,
) -> tuple[BoardService, BoardPlanningService]:
    """Share one session and board adapter across both board use cases."""

    board = SqlAlchemyBoardRepository(session)
    workspaces = SqlAlchemyTeamWorkspaceRepository(session)
    return (
        BoardService(
            cast(BoardRepositoryPort, board),
            cast(BoardCommandPort, SqlAlchemyBoardCommandRepository(board)),
            cast(TeamWorkspaceReadPort, workspaces),
        ),
        BoardPlanningService(
            cast(BoardRepositoryPort, board),
            cast(
                BoardPlanningCommandPort,
                SqlAlchemyBoardPlanningCommandRepository(board),
            ),
            cast(TeamWorkspaceReadPort, workspaces),
            cast(
                BoardIterationAnalyticsPort,
                SqlAlchemyBoardIterationAnalytics(session),
            ),
        ),
    )
