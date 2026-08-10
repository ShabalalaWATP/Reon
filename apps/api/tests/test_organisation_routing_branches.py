"""Route-selection validation and mutation branch coverage."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.errors import InvalidAction
from istari_service.models import RequestStatus, ServiceRequest
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    RequestRouteSelection,
    StaffingStatus,
)
from istari_service.repositories.organisation import (
    apply_routing_selection,
    clear_route_from,
    resolve_routing_selection,
)
from istari_service.schemas.work import (
    AllocateRequest,
    CompletionPayload,
    ProgressRequest,
    SendToAllocation,
)
from istari_service.work_command_types import RoutingSelection
from test_work_repository import make_request


def _request(status: RequestStatus) -> ServiceRequest:
    request = make_request(uuid4(), status)
    request.command_group = "old-command"
    request.ops_group = "old-ops"
    request.team_manager_group = "old-managers"
    request.team_analyst_group = "old-analysts"
    request.assigned_delivery_team = "Old Team"
    request.assigned_specialist_id = uuid4()
    request.awaiting_team_staffing = True
    return request


def _payload(status: RequestStatus, destination_id: UUID) -> CompletionPayload:
    if status is RequestStatus.TRIAGE_REVIEW:
        return ProgressRequest(
            action="progress",
            category="Research",
            priority="HIGH",
            destination_unit_id=destination_id,
        )
    if status is RequestStatus.COORDINATION_REVIEW:
        return SendToAllocation(
            action="send_to_allocation",
            destination_unit_id=destination_id,
            note="Route confirmed.",
        )
    return AllocateRequest(
        action="allocate",
        destination_unit_id=destination_id,
        required_capabilities=["Structured analysis"],
    )


def _unit(unit_id: UUID, kind: OrganisationKind) -> OrganisationUnit:
    is_team = kind is OrganisationKind.TEAM
    return OrganisationUnit(
        id=unit_id,
        code="SYNTHETIC_TEAM" if is_team else "SYNTHETIC_ROUTE",
        name="Synthetic Team" if is_team else "Synthetic Route",
        kind=kind,
        parent_id=uuid4(),
        staffing_status=(
            StaffingStatus.UNSTAFFED if is_team else StaffingStatus.ROUTING_POOL
        ),
        routing_candidate_group=None if is_team else "synthetic-routing",
        manager_candidate_group="synthetic-managers" if is_team else None,
        analyst_candidate_group="synthetic-analysts" if is_team else None,
        sort_order=1,
        is_configured=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "kind", "expected_position", "lock"),
    [
        (RequestStatus.TRIAGE_REVIEW, OrganisationKind.COMMAND, 1, False),
        (RequestStatus.COORDINATION_REVIEW, OrganisationKind.OPS_GROUP, 2, True),
        (RequestStatus.ALLOCATION_REVIEW, OrganisationKind.TEAM, 3, True),
    ],
)
async def test_resolve_routing_selection_maps_each_valid_stage(
    status: RequestStatus,
    kind: OrganisationKind,
    expected_position: int,
    lock: bool,
) -> None:
    destination_id = uuid4()
    unit = _unit(destination_id, kind)
    session = AsyncMock(spec=AsyncSession)
    session.scalar.side_effect = [uuid4(), None, unit]

    routing = await resolve_routing_selection(
        session,
        _request(status),
        _payload(status, destination_id),
        lock=lock,
    )

    assert routing is not None
    assert routing.unit_id == destination_id
    assert routing.position == expected_position
    assert routing.staffed is False
    assert routing.candidate_groups == (
        ("synthetic-managers", "synthetic-analysts")
        if kind is OrganisationKind.TEAM
        else ("synthetic-routing",)
    )


@pytest.mark.asyncio
async def test_resolve_routing_selection_handles_non_routing_and_denial_paths() -> None:
    destination_id = uuid4()
    payload = _payload(RequestStatus.TRIAGE_REVIEW, destination_id)
    session = AsyncMock(spec=AsyncSession)

    result = await resolve_routing_selection(
        session,
        _request(RequestStatus.IN_PROGRESS),
        payload,
        lock=False,
    )
    assert result is None
    session.scalar.assert_not_awaited()

    session.scalar.return_value = None
    with pytest.raises(InvalidAction, match="route is incomplete"):
        await resolve_routing_selection(
            session,
            _request(RequestStatus.TRIAGE_REVIEW),
            payload,
            lock=False,
        )

    session.reset_mock()
    session.scalar.side_effect = [uuid4(), None, None]
    with pytest.raises(InvalidAction, match="direct child"):
        await resolve_routing_selection(
            session,
            _request(RequestStatus.TRIAGE_REVIEW),
            payload,
            lock=False,
        )

    unsafe_unit = _unit(destination_id, OrganisationKind.COMMAND)
    unsafe_unit.routing_candidate_group = "Unsafe Group"
    session.reset_mock()
    session.scalar.side_effect = [uuid4(), None, unsafe_unit]
    with pytest.raises(InvalidAction, match="configured safely"):
        await resolve_routing_selection(
            session,
            _request(RequestStatus.TRIAGE_REVIEW),
            payload,
            lock=True,
        )


def _selection(position: int) -> RoutingSelection:
    groups = (
        ("new-managers", "new-analysts")
        if position == 3
        else (f"new-group-{position}",)
    )
    return RoutingSelection(
        unit_id=uuid4(),
        unit_code=f"ROUTE_{position}",
        unit_name=f"Route {position}",
        position=position,
        candidate_groups=groups,
        staffed=position != 3,
    )


@pytest.mark.asyncio
async def test_apply_routing_selection_ignores_an_absent_selection() -> None:
    session = AsyncMock(spec=AsyncSession)
    await apply_routing_selection(session, _request(RequestStatus.TRIAGE_REVIEW), None)
    session.execute.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("position", [1, 2, 3])
async def test_apply_routing_selection_replaces_downstream_state(position: int) -> None:
    session = AsyncMock(spec=AsyncSession)
    request = _request(RequestStatus.ALLOCATION_REVIEW)
    routing = _selection(position)

    await apply_routing_selection(session, request, routing)

    assert session.execute.await_count == 2
    added = session.add.call_args.args[0]
    assert isinstance(added, RequestRouteSelection)
    assert (added.request_id, added.unit_id, added.position) == (
        request.id,
        routing.unit_id,
        position,
    )
    if position == 1:
        assert request.command_group == "new-group-1"
        assert request.ops_group is None
        assert request.assigned_delivery_team is None
    elif position == 2:
        assert request.command_group == "old-command"
        assert request.ops_group == "new-group-2"
        assert request.assigned_delivery_team is None
    else:
        assert request.team_manager_group == "new-managers"
        assert request.team_analyst_group == "new-analysts"
        assert request.assigned_delivery_team == "Route 3"
        assert request.assigned_specialist_id is None
        assert request.awaiting_team_staffing is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("position", "cleared"),
    [
        (1, (True, True, True)),
        (2, (False, True, True)),
        (3, (False, False, True)),
        (4, (False, False, False)),
    ],
)
async def test_clear_route_only_clears_state_at_or_after_position(
    position: int,
    cleared: tuple[bool, bool, bool],
) -> None:
    session = AsyncMock(spec=AsyncSession)
    request = _request(RequestStatus.ALLOCATION_REVIEW)
    specialist_id = request.assigned_specialist_id

    await clear_route_from(session, request, position)

    assert session.execute.await_count == (2 if position <= 3 else 1)
    assert (request.command_group is None) is cleared[0]
    assert (request.ops_group is None) is cleared[1]
    assert (request.assigned_delivery_team is None) is cleared[2]
    if cleared[2]:
        assert request.team_manager_group is None
        assert request.team_analyst_group is None
        assert request.assigned_specialist_id is None
        assert request.awaiting_team_staffing is False
    else:
        assert request.team_manager_group == "old-managers"
        assert request.team_analyst_group == "old-analysts"
        assert request.assigned_specialist_id == specialist_id
        assert request.awaiting_team_staffing is True
