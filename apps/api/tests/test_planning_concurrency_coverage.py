"""Focused failure-path coverage for planning concurrency controls."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import istari_service.repositories.board as board_module
from istari_service.board_models import (
    ReservationStatus,
    WorkPackagePriority,
    WorkPackageStatus,
)
from istari_service.domain import Actor
from istari_service.errors import (
    BoardItemNotFound,
    InvalidBoardChange,
    StaleVersion,
    TeamWorkspaceNotFound,
)
from istari_service.models import UserRole
from istari_service.repositories.board import SqlAlchemyBoardRepository
from istari_service.repositories.board_planning_commands import (
    SqlAlchemyBoardPlanningCommandRepository,
    _constraint_name,
)
from istari_service.schemas.board import (
    IterationCloseCommand,
    ReservationCancelCommand,
    ReservationCommand,
    WorkPackageCommand,
)
from istari_service.services.board_service import BoardService


class _Nested(AbstractAsyncContextManager[None]):
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class _Session:
    def __init__(self, *scalars: object) -> None:
        self.scalars = iter(scalars)
        self.added: list[object] = []
        self.flush_error: BaseException | None = None

    async def scalar(self, _statement: object) -> object:
        return next(self.scalars)

    async def execute(self, _statement: object) -> object:
        row = next(self.scalars)
        return SimpleNamespace(one_or_none=lambda: row)

    def add(self, item: object) -> None:
        self.added.append(item)

    def begin_nested(self) -> _Nested:
        return _Nested()

    async def flush(self) -> None:
        if self.flush_error:
            raise self.flush_error


def _repository(session: _Session) -> SqlAlchemyBoardRepository:
    return SqlAlchemyBoardRepository(cast(AsyncSession, session))


async def test_board_repository_missing_and_false_read_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = SimpleNamespace()
    session = _Session((request, None), None, None, None)
    repository = _repository(session)
    monkeypatch.setattr(board_module, "request_projection", lambda *_args: None)

    with pytest.raises(BoardItemNotFound):
        await repository.request_item(uuid4(), uuid4())
    with pytest.raises(BoardItemNotFound):
        await repository.locked_package(uuid4(), uuid4(), 1)
    with pytest.raises(TeamWorkspaceNotFound):
        await repository.lock_planning_aggregate(uuid4())
    assert not await repository.request_belongs_to_team(uuid4(), uuid4())

    absent = _repository(_Session(None))
    with pytest.raises(BoardItemNotFound):
        await absent.request_item(uuid4(), uuid4())

    expected_item = object()
    successful = _repository(_Session((request, "Synthetic owner")))
    monkeypatch.setattr(
        board_module,
        "request_projection",
        lambda *_args: SimpleNamespace(item=expected_item),
    )
    assert await successful.request_item(uuid4(), uuid4()) is expected_item

    successful._page_reads.projected = AsyncMock(return_value=[])  # type: ignore[method-assign]
    assert await successful.projected_items(uuid4()) == []


def _package() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), team_id=uuid4(), version=1)


def _reservation_command() -> ReservationCommand:
    starts_at = datetime.now(UTC) + timedelta(days=1)
    return ReservationCommand(
        userId=uuid4(),
        startsAt=starts_at,
        endsAt=starts_at + timedelta(hours=1),
        reason="Reserve a synthetic planning window for focused delivery.",
    )


def _integrity_error(constraint_name: str | None) -> IntegrityError:
    original = RuntimeError("synthetic database conflict")
    if constraint_name:
        original.constraint_name = constraint_name  # type: ignore[attr-defined]
    return IntegrityError("insert", {}, original)


async def test_reservation_named_constraint_maps_and_unrelated_error_propagates() -> (
    None
):
    for constraint, expected in (
        ("capacity_reservations_active_no_overlap", InvalidBoardChange),
        ("unrelated_constraint", IntegrityError),
    ):
        session = _Session(None)
        session.flush_error = _integrity_error(constraint)
        commands = SqlAlchemyBoardPlanningCommandRepository(
            SimpleNamespace(session=cast(AsyncSession, session))
        )
        with pytest.raises(expected):
            await commands.create_reservation(
                _package(),
                uuid4(),
                _reservation_command(),  # type: ignore[arg-type]
            )


async def test_reservation_cancel_missing_stale_and_success_paths() -> None:
    actor_id, reservation_id = uuid4(), uuid4()
    command = ReservationCancelCommand(
        expectedVersion=2,
        reason="Cancel this synthetic reservation after explicit replanning.",
    )
    package = _package()
    missing = SqlAlchemyBoardPlanningCommandRepository(
        SimpleNamespace(session=cast(AsyncSession, _Session(None)))
    )
    with pytest.raises(BoardItemNotFound):
        await missing.cancel_reservation(package, reservation_id, actor_id, command)

    reservation = SimpleNamespace(version=1, status=ReservationStatus.ACTIVE)
    stale = SqlAlchemyBoardPlanningCommandRepository(
        SimpleNamespace(session=cast(AsyncSession, _Session(reservation)))
    )
    with pytest.raises(StaleVersion):
        await stale.cancel_reservation(package, reservation_id, actor_id, command)

    reservation.version = 2
    session = _Session(reservation)
    commands = SqlAlchemyBoardPlanningCommandRepository(
        SimpleNamespace(session=cast(AsyncSession, session))
    )
    result = await commands.cancel_reservation(
        package, reservation_id, actor_id, command
    )
    assert result.status is ReservationStatus.CANCELLED
    assert result.cancelled_by_user_id == actor_id
    assert package.version == 2
    assert len(session.added) == 1


async def test_iteration_stale_version_path() -> None:
    iteration = SimpleNamespace(version=1)
    commands = SqlAlchemyBoardPlanningCommandRepository(
        SimpleNamespace(session=cast(AsyncSession, _Session(iteration)))
    )
    with pytest.raises(StaleVersion):
        await commands.close_iteration(
            uuid4(),
            uuid4(),
            IterationCloseCommand(
                grantId=uuid4(),
                expectedVersion=2,
                completionSummary=(
                    "Close the synthetic iteration after its recorded version changed."
                ),
            ),
        )


async def test_constraint_extractor_handles_cycles_and_non_exception_wrappers() -> None:
    cyclic = RuntimeError("cyclic wrapper")
    cyclic.__cause__ = cyclic
    cyclic.orig = "not an exception"  # type: ignore[attr-defined]
    assert _constraint_name(cyclic) is None


def _work_command(**updates: Any) -> WorkPackageCommand:
    values: dict[str, Any] = {
        "title": "Synthetic package",
        "description": "A fictional package for planning validation coverage.",
        "ownerUserId": uuid4(),
        "contributorIds": [],
        "estimatePoints": 3,
        "remainingEffortMinutes": 60,
        "dueOn": datetime.now(UTC).date() + timedelta(days=3),
        "priority": WorkPackagePriority.MEDIUM,
        "blockers": "No synthetic blockers.",
        "acceptanceCriteria": "The focused planning checks pass.",
        "linkedRequestId": None,
        "dependencyIds": [],
        "iterationId": None,
    }
    values.update(updates)
    return WorkPackageCommand(**values)


async def test_service_link_validation_and_non_wip_target_paths() -> None:
    board = SimpleNamespace(
        session=cast(AsyncSession, _Session()),
        current_member_ids=AsyncMock(return_value=set()),
        package_ids_in_team=AsyncMock(return_value=set()),
        request_belongs_to_team=AsyncMock(return_value=False),
        request_requester_id=AsyncMock(return_value=None),
        lock_planning_aggregate=AsyncMock(),
    )
    service = BoardService(board, SimpleNamespace(), SimpleNamespace())
    actor = SimpleNamespace(id=uuid4())
    linked = uuid4()
    command = _work_command(linkedRequestId=linked)
    board.current_member_ids.return_value = {command.owner_user_id}
    with pytest.raises(BoardItemNotFound):
        await service._package_policy.validate_links(actor, uuid4(), command)
    board.request_belongs_to_team.assert_awaited_once()

    package = SimpleNamespace(id=uuid4())
    await service._package_policy.enforce_wip(
        uuid4(), package, cast(WorkPackageStatus, object())
    )
    board.lock_planning_aggregate.assert_not_awaited()


async def test_service_link_validation_excludes_requester_stable_identity() -> None:
    requester_id, other_id, team_id, request_id = uuid4(), uuid4(), uuid4(), uuid4()
    board = SimpleNamespace(
        session=cast(AsyncSession, _Session()),
        current_member_ids=AsyncMock(return_value={requester_id, other_id}),
        package_ids_in_team=AsyncMock(return_value=set()),
        request_belongs_to_team=AsyncMock(return_value=True),
        request_requester_id=AsyncMock(return_value=requester_id),
        iteration_in_team=AsyncMock(),
    )
    service = BoardService(board, SimpleNamespace(), SimpleNamespace())

    own = _work_command(ownerUserId=other_id, linkedRequestId=request_id)
    with pytest.raises(BoardItemNotFound):
        await service._package_policy.validate_links(
            SimpleNamespace(id=requester_id), team_id, own
        )

    requester_owned = _work_command(
        ownerUserId=requester_id, linkedRequestId=request_id
    )
    with pytest.raises(BoardItemNotFound):
        await service._package_policy.validate_links(
            SimpleNamespace(id=other_id), team_id, requester_owned
        )

    requester_contributes = _work_command(
        ownerUserId=other_id,
        contributorIds=[requester_id],
        linkedRequestId=request_id,
    )
    with pytest.raises(BoardItemNotFound):
        await service._package_policy.validate_links(
            SimpleNamespace(id=other_id), team_id, requester_contributes
        )

    allowed = _work_command(ownerUserId=other_id, linkedRequestId=request_id)
    await service._package_policy.validate_links(
        SimpleNamespace(id=uuid4()), team_id, allowed
    )


async def test_service_create_rejects_cycle_after_aggregate_lock() -> None:
    team_id, actor_id, package_id = uuid4(), uuid4(), uuid4()
    board = SimpleNamespace(
        session=cast(AsyncSession, _Session()),
        lock_planning_aggregate=AsyncMock(),
    )
    commands = SimpleNamespace(
        create_package=AsyncMock(return_value=SimpleNamespace(id=package_id)),
        dependency_cycle=AsyncMock(return_value=True),
    )
    service = BoardService(board, commands, SimpleNamespace())
    service._package_policy.authorise_create = AsyncMock()  # type: ignore[method-assign]
    service._package_policy.validate_links = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(InvalidBoardChange, match="dependencies cannot contain"):
        await service.create_package(
            Actor(
                actor_id,
                "synthetic-specialist",
                "Synthetic Specialist",
                UserRole.DELIVERY_SPECIALIST,
                "SSG Team",
            ),
            team_id,
            _work_command(),
        )
    board.lock_planning_aggregate.assert_awaited_once_with(team_id)
