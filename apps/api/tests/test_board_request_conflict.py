"""Stable requester exclusion across every linked board-package mutation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import istari_service.services.board_planning_service as planning_module
import istari_service.services.board_service as board_module
from istari_service.board_models import WorkPackageStatus
from istari_service.domain import Actor
from istari_service.errors import BoardItemNotFound
from istari_service.models import UserRole
from istari_service.schemas.board import (
    ReservationCancelCommand,
    ReservationCommand,
    WorkPackageMove,
)
from istari_service.services.board_planning_service import BoardPlanningService
from istari_service.services.board_service import BoardService


def _actor(actor_id: object) -> Actor:
    return Actor(
        actor_id,  # type: ignore[arg-type]
        "dual-context-specialist",
        "Dual Context Specialist",
        UserRole.DELIVERY_SPECIALIST,
        "SSG Team",
    )


def _board(actor_id: object) -> tuple[SimpleNamespace, SimpleNamespace]:
    package = SimpleNamespace(
        id=uuid4(),
        linked_request_id=uuid4(),
        owner_user_id=uuid4(),
        status=WorkPackageStatus.BACKLOG,
    )
    board = SimpleNamespace(
        session=SimpleNamespace(),
        locked_package=AsyncMock(return_value=package),
        request_requester_id=AsyncMock(return_value=actor_id),
        package_contributor_ids=AsyncMock(return_value=set()),
    )
    return board, package


async def test_requester_cannot_move_own_linked_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_id, team_id = uuid4(), uuid4()
    board, package = _board(actor_id)
    monkeypatch.setattr(board_module, "authorise_package_change", AsyncMock())
    service = BoardService(board, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(BoardItemNotFound):
        await service.move_package(
            _actor(actor_id),
            team_id,
            package.id,
            WorkPackageMove(
                expectedVersion=1,
                target=WorkPackageStatus.READY,
                reason="Move this synthetic package into prepared work.",
            ),
        )


@pytest.mark.parametrize("operation", ["reserve", "cancel"])
async def test_requester_cannot_change_own_linked_package_reservations(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    actor_id, team_id = uuid4(), uuid4()
    board, package = _board(actor_id)
    monkeypatch.setattr(planning_module, "authorise_package_change", AsyncMock())
    service = BoardPlanningService(
        board, SimpleNamespace(), SimpleNamespace(), SimpleNamespace()
    )
    if operation == "reserve":
        start = datetime.now(UTC) + timedelta(days=1)
        command = ReservationCommand(
            userId=uuid4(),
            startsAt=start,
            endsAt=start + timedelta(hours=1),
            reason="Reserve focused time for this synthetic package.",
        )
        call = service.reserve(_actor(actor_id), team_id, package.id, 1, command)
    else:
        command = ReservationCancelCommand(
            expectedVersion=1,
            reason="Cancel this synthetic package reservation safely.",
        )
        call = service.cancel_reservation(
            _actor(actor_id), team_id, package.id, uuid4(), 1, command
        )
    with pytest.raises(BoardItemNotFound):
        await call


async def test_requester_cannot_be_reservation_subject_on_linked_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_id, requester_id, team_id = uuid4(), uuid4(), uuid4()
    board, package = _board(requester_id)
    monkeypatch.setattr(planning_module, "authorise_package_change", AsyncMock())
    service = BoardPlanningService(
        board, SimpleNamespace(), SimpleNamespace(), SimpleNamespace()
    )
    start = datetime.now(UTC) + timedelta(days=1)
    command = ReservationCommand(
        userId=requester_id,
        startsAt=start,
        endsAt=start + timedelta(hours=1),
        reason="Reserve focused time for this synthetic package.",
    )

    with pytest.raises(BoardItemNotFound):
        await service.reserve(_actor(actor_id), team_id, package.id, 1, command)
