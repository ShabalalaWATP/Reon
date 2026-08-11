"""Defensive branch tests for production clarification persistence rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from istari_service.clarification_models import ClarificationStatus
from istari_service.domain import Actor
from istari_service.errors import InvalidAction
from istari_service.models import RequestStatus, UserRole
from istari_service.repositories.clarifications import (
    apply_clarification_effect,
    validate_clarification_effect,
    withdraw_open_clarification,
)
from istari_service.schemas.work import ProvideClarification, RequestClarification


def _actor(user_id=None) -> Actor:
    return Actor(
        user_id or uuid4(),
        "analyst@example.test",
        "Synthetic Analyst",
        UserRole.DELIVERY_SPECIALIST,
        "SSG Team",
    )


def _request(actor: Actor, **updates: object) -> SimpleNamespace:
    values = {
        "id": uuid4(),
        "status": RequestStatus.IN_PROGRESS,
        "assigned_specialist_id": actor.id,
        "requester_id": uuid4(),
        "required_by": datetime.now(UTC).date() + timedelta(days=7),
    }
    values.update(updates)
    return SimpleNamespace(**values)


def _request_command(**updates: object) -> RequestClarification:
    values = {
        "action": "request_clarification",
        "question": "Which fictional region should be prioritised?",
        "reason": "The scope is required to complete the product.",
        "response_deadline": datetime.now(UTC).date() + timedelta(days=2),
    }
    values.update(updates)
    return RequestClarification(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("request_updates", "command_updates", "open_thread"),
    [
        ({"status": RequestStatus.LEAD_REVIEW}, {}, None),
        ({"assigned_specialist_id": uuid4()}, {}, None),
        ({}, {"response_deadline": datetime.now(UTC).date() - timedelta(days=1)}, None),
        ({}, {"response_deadline": datetime.now(UTC).date() + timedelta(days=8)}, None),
        ({}, {}, uuid4()),
    ],
)
async def test_request_validation_rejects_each_stale_or_invalid_condition(
    request_updates: dict[str, object],
    command_updates: dict[str, object],
    open_thread: object,
) -> None:
    actor = _actor()
    request = _request(actor, **request_updates)
    session = SimpleNamespace(scalar=AsyncMock(return_value=open_thread))
    with pytest.raises(InvalidAction, match="cannot be opened"):
        await validate_clarification_effect(
            session,
            request,
            actor,
            _request_command(**command_updates),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_request_validation_and_creation_accept_valid_state() -> None:
    actor = _actor()
    request = _request(actor)
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[None, 2]),
        add=Mock(),
        flush=AsyncMock(),
    )
    command = _request_command()
    await validate_clarification_effect(session, request, actor, command)  # type: ignore[arg-type]
    await apply_clarification_effect(session, request, actor, command)  # type: ignore[arg-type]
    assert session.add.call_count == 2
    assert session.add.call_args_list[0].args[0].sequence == 3


@pytest.mark.asyncio
async def test_creation_requires_an_assigned_analyst() -> None:
    actor = _actor()
    request = _request(actor, assigned_specialist_id=None)
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    with pytest.raises(InvalidAction, match="assigned Analyst"):
        await apply_clarification_effect(
            session,
            request,
            actor,
            _request_command(),  # type: ignore[arg-type]
        )


def _open_thread(request: SimpleNamespace, *, version: int = 3) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        request_id=request.id,
        version=version,
        assigned_specialist_id=request.assigned_specialist_id,
        status=ClarificationStatus.OPEN,
        closed_at=None,
    )


def _response(thread: SimpleNamespace, **updates: object) -> ProvideClarification:
    values = {
        "action": "provide_clarification",
        "thread_id": thread.id,
        "expected_version": thread.version,
        "information": "A complete fictional response.",
    }
    values.update(updates)
    return ProvideClarification(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    ["status", "requester", "missing", "version", "specialist"],
)
async def test_response_validation_rejects_each_invalid_condition(
    failure: str,
) -> None:
    customer = _actor()
    request = _request(
        customer,
        status=RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
        requester_id=customer.id,
    )
    thread = _open_thread(request)
    response = _response(thread)
    if failure == "status":
        request.status = RequestStatus.IN_PROGRESS
    elif failure == "requester":
        request.requester_id = uuid4()
    elif failure == "missing":
        thread = None
    elif failure == "version":
        response = _response(thread, expected_version=thread.version + 1)
    else:
        thread.assigned_specialist_id = uuid4()
    session = SimpleNamespace(scalar=AsyncMock(return_value=thread))
    with pytest.raises(InvalidAction, match="no longer current"):
        await validate_clarification_effect(
            session,
            request,
            customer,
            response,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_response_validation_and_application_close_thread() -> None:
    customer = _actor()
    request = _request(
        customer,
        status=RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
        requester_id=customer.id,
    )
    thread = _open_thread(request)
    session = SimpleNamespace(scalar=AsyncMock(return_value=thread), add=Mock())
    response = _response(thread)
    await validate_clarification_effect(session, request, customer, response)  # type: ignore[arg-type]
    await apply_clarification_effect(session, request, customer, response)  # type: ignore[arg-type]
    assert thread.status is ClarificationStatus.ANSWERED
    assert thread.version == 4
    assert session.add.call_args.args[0].sequence == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", [None, SimpleNamespace(version=4)])
async def test_response_application_rechecks_locked_thread(stored: object) -> None:
    customer = _actor()
    request = _request(customer)
    current = SimpleNamespace(id=uuid4(), version=3)
    session = SimpleNamespace(scalar=AsyncMock(return_value=stored))
    with pytest.raises(InvalidAction, match="no longer current"):
        await apply_clarification_effect(
            session,
            request,
            customer,
            _response(current),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_withdrawal_ignores_other_states_and_rejects_missing_thread() -> None:
    actor = _actor()
    request = _request(actor)
    untouched = SimpleNamespace(scalar=AsyncMock())
    await withdraw_open_clarification(
        untouched,
        request,
        actor,
        "No longer needed.",  # type: ignore[arg-type]
    )
    untouched.scalar.assert_not_awaited()

    request.status = RequestStatus.CUSTOMER_INFORMATION_REQUIRED
    missing = SimpleNamespace(scalar=AsyncMock(return_value=None))
    with pytest.raises(InvalidAction, match="no longer open"):
        await withdraw_open_clarification(
            missing,
            request,
            actor,
            "No longer needed.",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_withdrawal_closes_the_locked_open_thread() -> None:
    actor = _actor()
    request = _request(actor, status=RequestStatus.CUSTOMER_INFORMATION_REQUIRED)
    thread = _open_thread(request)
    session = SimpleNamespace(scalar=AsyncMock(return_value=thread), add=Mock())
    await withdraw_open_clarification(
        session,
        request,
        actor,
        "The fictional need ended.",  # type: ignore[arg-type]
    )
    assert thread.status is ClarificationStatus.WITHDRAWN
    assert thread.version == 4
    assert session.add.call_args.args[0].sequence == 2
