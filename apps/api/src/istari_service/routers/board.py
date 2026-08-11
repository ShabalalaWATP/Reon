"""Exact-team workflow board and independent planning routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from istari_service.board_models import BoardColumn
from istari_service.dependencies import CurrentActor, DatabaseSession, MutationActor
from istari_service.repositories.board import SqlAlchemyBoardRepository
from istari_service.repositories.team_workspaces import (
    SqlAlchemyTeamWorkspaceRepository,
)
from istari_service.schemas.board import (
    BoardConfigurationCommand,
    BoardConfigurationResult,
    BoardFilters,
    BoardItem,
    BoardItemType,
    BoardMoveAttempt,
    BoardResult,
    DeleteSavedViewCommand,
    IterationCloseCommand,
    IterationCommand,
    IterationList,
    IterationResult,
    ReservationCancelCommand,
    ReservationCommand,
    SavedBoardViewCommand,
    SavedBoardViewResult,
    SavedBoardViewUpdate,
    WorkPackageCommand,
    WorkPackageList,
    WorkPackageMove,
    WorkPackageResult,
    WorkPackageUpdate,
)
from istari_service.services.board_planning_service import BoardPlanningService
from istari_service.services.board_service import BoardService

router = APIRouter(prefix="/team-workspaces", tags=["team-board"])


def _services(
    session: DatabaseSession,
) -> tuple[BoardService, BoardPlanningService]:
    board = SqlAlchemyBoardRepository(session)
    workspaces = SqlAlchemyTeamWorkspaceRepository(session)
    return BoardService(board, workspaces), BoardPlanningService(board, workspaces)


@router.get("/{team_id}/board", response_model=BoardResult)
async def get_board(
    team_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    search: Annotated[str, Query(max_length=120)] = "",
    column: Annotated[list[BoardColumn] | None, Query()] = None,
    priority: Annotated[list[str] | None, Query()] = None,
    owner_id: Annotated[UUID | None, Query(alias="ownerId")] = None,
    item_type: Annotated[list[BoardItemType] | None, Query(alias="itemType")] = None,
    due_before: Annotated[date | None, Query(alias="dueBefore")] = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> BoardResult:
    service, _ = _services(session)
    return await service.board(
        actor,
        team_id,
        BoardFilters(
            search=search,
            columns=column or [],
            priorities=priority or [],
            owner_user_id=owner_id,
            item_types=item_type or [],
            due_before=due_before,
        ),
        cursor,
        limit,
    )


@router.get("/{team_id}/board/requests/{request_id}", response_model=BoardItem)
async def get_board_request(
    team_id: UUID,
    request_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
) -> BoardItem:
    service, _ = _services(session)
    return await service.board_request(actor, team_id, request_id)


@router.post("/{team_id}/board/moves", response_model=WorkPackageResult)
async def move_board_item(
    team_id: UUID,
    command: BoardMoveAttempt,
    actor: MutationActor,
    session: DatabaseSession,
) -> WorkPackageResult:
    service, _ = _services(session)
    return await service.move_board_item(actor, team_id, command)


@router.put("/{team_id}/board/configuration", response_model=BoardConfigurationResult)
async def configure_board(
    team_id: UUID,
    command: BoardConfigurationCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> BoardConfigurationResult:
    service, _ = _services(session)
    return await service.configure(actor, team_id, command)


@router.post("/{team_id}/board/saved-views", response_model=SavedBoardViewResult)
async def create_saved_view(
    team_id: UUID,
    command: SavedBoardViewCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> SavedBoardViewResult:
    service, _ = _services(session)
    return await service.create_saved_view(actor, team_id, command)


@router.put(
    "/{team_id}/board/saved-views/{view_id}", response_model=SavedBoardViewResult
)
async def update_saved_view(
    team_id: UUID,
    view_id: UUID,
    command: SavedBoardViewUpdate,
    actor: MutationActor,
    session: DatabaseSession,
) -> SavedBoardViewResult:
    service, _ = _services(session)
    return await service.update_saved_view(actor, team_id, view_id, command)


@router.delete(
    "/{team_id}/board/saved-views/{view_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_saved_view(
    team_id: UUID,
    view_id: UUID,
    command: DeleteSavedViewCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> Response:
    service, _ = _services(session)
    await service.delete_saved_view(actor, team_id, view_id, command)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{team_id}/packages", response_model=WorkPackageList)
async def list_packages(
    team_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> WorkPackageList:
    service, _ = _services(session)
    return await service.packages(actor, team_id, limit)


@router.get("/{team_id}/packages/{package_id}", response_model=WorkPackageResult)
async def get_package(
    team_id: UUID,
    package_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
) -> WorkPackageResult:
    service, _ = _services(session)
    return await service.package(actor, team_id, package_id)


@router.post("/{team_id}/packages", response_model=WorkPackageResult)
async def create_package(
    team_id: UUID,
    command: WorkPackageCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> WorkPackageResult:
    service, _ = _services(session)
    return await service.create_package(actor, team_id, command)


@router.put("/{team_id}/packages/{package_id}", response_model=WorkPackageResult)
async def update_package(
    team_id: UUID,
    package_id: UUID,
    command: WorkPackageUpdate,
    actor: MutationActor,
    session: DatabaseSession,
) -> WorkPackageResult:
    service, _ = _services(session)
    return await service.update_package(actor, team_id, package_id, command)


@router.post("/{team_id}/packages/{package_id}/move", response_model=WorkPackageResult)
async def move_package(
    team_id: UUID,
    package_id: UUID,
    command: WorkPackageMove,
    actor: MutationActor,
    session: DatabaseSession,
) -> WorkPackageResult:
    service, _ = _services(session)
    return await service.move_package(actor, team_id, package_id, command)


@router.post(
    "/{team_id}/packages/{package_id}/reservations",
    response_model=WorkPackageResult,
)
async def create_reservation(
    team_id: UUID,
    package_id: UUID,
    command: ReservationCommand,
    package_version: Annotated[int, Query(alias="packageVersion", ge=1)],
    actor: MutationActor,
    session: DatabaseSession,
) -> WorkPackageResult:
    _, service = _services(session)
    return await service.reserve(actor, team_id, package_id, package_version, command)


@router.post(
    "/{team_id}/packages/{package_id}/reservations/{reservation_id}/cancel",
    response_model=WorkPackageResult,
)
async def cancel_reservation(
    team_id: UUID,
    package_id: UUID,
    reservation_id: UUID,
    command: ReservationCancelCommand,
    package_version: Annotated[int, Query(alias="packageVersion", ge=1)],
    actor: MutationActor,
    session: DatabaseSession,
) -> WorkPackageResult:
    _, service = _services(session)
    return await service.cancel_reservation(
        actor, team_id, package_id, reservation_id, package_version, command
    )


@router.get("/{team_id}/iterations", response_model=IterationList)
async def list_iterations(
    team_id: UUID, actor: CurrentActor, session: DatabaseSession
) -> IterationList:
    _, service = _services(session)
    return await service.iterations(actor, team_id)


@router.post("/{team_id}/iterations", response_model=IterationResult)
async def create_iteration(
    team_id: UUID,
    command: IterationCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> IterationResult:
    _, service = _services(session)
    return await service.create_iteration(actor, team_id, command)


@router.post(
    "/{team_id}/iterations/{iteration_id}/close", response_model=IterationResult
)
async def close_iteration(
    team_id: UUID,
    iteration_id: UUID,
    command: IterationCloseCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> IterationResult:
    _, service = _services(session)
    return await service.close_iteration(actor, team_id, iteration_id, command)


from istari_service.routers import planning as _planning  # noqa: E402

router.include_router(_planning.router)
