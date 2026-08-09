"""Focused fail-closed coverage for routing and work-command validation."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

import istari_service.workflow_command_state as command_state_module
from istari_service.domain import WorkRecord
from istari_service.errors import AlreadyClaimed, InvalidAction, ObjectNotFound
from istari_service.models import (
    RequestStatus,
    UserRole,
    WorkflowTaskStatus,
)
from istari_service.schemas.organisation import RoutingOptionsWorkspace
from istari_service.schemas.work import (
    CloseRequest,
    CompletionPayload,
    ProgressRequest,
)
from istari_service.services.work_service import WorkService
from istari_service.work_command_types import (
    RoutingSelection,
    WorkCommandType,
    command_payload,
    parse_command,
)
from istari_service.workflow.types import (
    CompleteTaskCommand,
    WorkflowAction,
    WorkflowRouteSelection,
)
from istari_service.workflow_command_state import validated_command_state
from test_coverage_services_work_claim import (
    FakeCommandDispatcher,
    FakeWorkRepository,
    actor,
    bundle,
)
from test_workflow_command_state_edges import StateSession, _state

WORK_ID = UUID("00000000-0000-4000-8000-000000000101")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000102")
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000103")
OUTBOX_ID = UUID("00000000-0000-4000-8000-000000000104")
UNIT_ID = UUID("00000000-0000-4000-8000-000000000105")
OTHER_ID = UUID("00000000-0000-4000-8000-000000000106")


def routing(**changes: object) -> RoutingSelection:
    values: dict[str, object] = {
        "unit_id": UNIT_ID,
        "unit_code": "SYNTHETIC_UNIT",
        "unit_name": "Synthetic Unit",
        "position": 1,
        "candidate_groups": ("synthetic-group",),
        "staffed": True,
    }
    values.update(changes)
    return RoutingSelection(**values)  # type: ignore[arg-type]


def payload(
    *,
    completion: CompletionPayload | None = None,
    selected_route: RoutingSelection | None = None,
) -> dict[str, Any]:
    return command_payload(
        work_id=WORK_ID,
        task_key="task-1",
        process_instance_key="process-1",
        element_id="intake_review",
        actor_id=ACTOR_ID,
        request_version=1,
        request_status=RequestStatus.TRIAGE_REVIEW,
        completion=completion,
        routing=selected_route,
    )


def malformed_route(value: object) -> dict[str, Any]:
    stored = payload()
    stored["routing"] = value
    return stored


def close_request() -> CloseRequest:
    return CloseRequest(action="close", reason="Synthetic closure reason.")


def progress_request() -> ProgressRequest:
    return ProgressRequest(
        action="progress",
        category="Research",
        priority="LOW",
        destination_unit_id=UNIT_ID,
    )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: routing(unit_code=" "),
        lambda: routing(unit_name=" "),
        lambda: routing(position=0),
        lambda: routing(candidate_groups=()),
        lambda: routing(candidate_groups=(" ",)),
    ],
)
def test_routing_selection_rejects_empty_or_invalid_fields(
    factory: Callable[[], RoutingSelection],
) -> None:
    with pytest.raises(ValueError):
        factory()


ROUTE_VALUES = {
    "unitId": str(UNIT_ID),
    "unitCode": "SYNTHETIC_UNIT",
    "unitName": "Synthetic Unit",
    "position": 1,
    "candidateGroups": ["synthetic-group"],
    "staffed": True,
}


@pytest.mark.parametrize(
    ("event_type", "stored", "message"),
    [
        (WorkCommandType.COMPLETE_TASK.value, payload(), "completion payload"),
        (
            WorkCommandType.CLAIM_TASK.value,
            payload(completion=close_request()),
            "claim commands",
        ),
        (
            WorkCommandType.CLAIM_TASK.value,
            payload(selected_route=routing()),
            "claim commands",
        ),
        (WorkCommandType.CLAIM_TASK.value, malformed_route("route"), "object"),
        (
            WorkCommandType.CLAIM_TASK.value,
            malformed_route({**ROUTE_VALUES, "candidateGroups": ("group",)}),
            "must be strings",
        ),
        (
            WorkCommandType.CLAIM_TASK.value,
            malformed_route({**ROUTE_VALUES, "candidateGroups": [1]}),
            "must be strings",
        ),
        (
            WorkCommandType.COMPLETE_TASK.value,
            payload(completion=close_request(), selected_route=routing()),
            "not valid",
        ),
        (
            WorkCommandType.COMPLETE_TASK.value,
            payload(completion=progress_request()),
            "does not match",
        ),
        (
            WorkCommandType.COMPLETE_TASK.value,
            payload(completion=progress_request(), selected_route=routing(position=2)),
            "does not match",
        ),
    ],
)
def test_parse_command_rejects_invalid_completion_routing_contracts(
    event_type: str,
    stored: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_command(OUTBOX_ID, event_type, stored, attempts=1)


def workflow_route(**changes: object) -> WorkflowRouteSelection:
    values: dict[str, object] = {
        "unit_id": UNIT_ID,
        "unit_code": "SYNTHETIC_UNIT",
        "candidate_groups": ("synthetic-group",),
    }
    values.update(changes)
    return WorkflowRouteSelection(**values)  # type: ignore[arg-type]


def complete_command(**changes: object) -> CompleteTaskCommand:
    values: dict[str, object] = {
        "task_key": "task-1",
        "process_instance_key": "process-1",
        "expected_element_id": "intake_review",
        "action": WorkflowAction.PROGRESS,
    }
    values.update(changes)
    return CompleteTaskCommand(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "factory",
    [
        lambda: workflow_route(unit_code=" "),
        lambda: workflow_route(candidate_groups=()),
        lambda: workflow_route(candidate_groups=(" ",)),
        lambda: complete_command(route_selection=object()),
        lambda: complete_command(
            action=WorkflowAction.CLOSE,
            route_selection=workflow_route(),
        ),
        lambda: complete_command(
            route_selection=workflow_route(
                candidate_groups=("synthetic-group", "second-group")
            )
        ),
    ],
)
def test_workflow_route_values_reject_invalid_contracts(
    factory: Callable[[], object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        factory()


async def test_command_state_rejects_a_changed_resolved_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command, task, request, user, instance = _state(
        command_type=WorkCommandType.COMPLETE_TASK,
        completion=close_request(),
    )

    async def changed_route(*_args: object, **_kwargs: object) -> RoutingSelection:
        return routing()

    monkeypatch.setattr(
        command_state_module,
        "resolve_routing_selection",
        changed_route,
    )
    with pytest.raises(InvalidAction):
        await validated_command_state(  # type: ignore[arg-type]
            StateSession([task, request, user, instance]), command, request.id
        )


class RoutingRepository(FakeWorkRepository):
    routed_work: WorkRecord | None = None

    async def routing_options(
        self,
        work: WorkRecord,
    ) -> RoutingOptionsWorkspace:
        self.routed_work = work
        return RoutingOptionsWorkspace(route=[], items=[])


async def test_work_service_routing_options_are_concealed_until_valid() -> None:
    triage = actor(UserRole.INTAKE_TRIAGE)
    repository = RoutingRepository()
    service = WorkService(repository, FakeCommandDispatcher(repository))
    with pytest.raises(ObjectNotFound):
        await service.routing_options(triage, WORK_ID)

    repository.value = bundle(triage, assignee_id=OTHER_ID)
    with pytest.raises(ObjectNotFound):
        await service.routing_options(triage, repository.value.record.id)

    requester = actor(UserRole.REQUESTER)
    repository.value = bundle(
        requester,
        status=RequestStatus.INFORMATION_REQUIRED,
        requester_id=requester.id,
    )
    with pytest.raises(ObjectNotFound):
        await service.routing_options(requester, repository.value.record.id)

    repository.value = bundle(triage)
    assert await service.routing_options(
        triage, repository.value.record.id
    ) == RoutingOptionsWorkspace(route=[], items=[])
    assert repository.routed_work is repository.value.record


async def test_work_service_rejects_missing_claim_projection_and_open_completion() -> (
    None
):
    triage = actor(UserRole.INTAKE_TRIAGE)
    repository = FakeWorkRepository(bundle(triage))

    async def processed_without_projection(_outbox_id: UUID) -> bool:
        return True

    dispatcher = SimpleNamespace(dispatch=processed_without_projection)
    service = WorkService(repository, dispatcher)  # type: ignore[arg-type]
    assert repository.value is not None
    with pytest.raises(AlreadyClaimed):
        await service.claim(triage, repository.value.record.id)
    assert repository.value.record.task_status is WorkflowTaskStatus.CLAIM_PENDING

    repository = FakeWorkRepository(bundle(triage))
    service = WorkService(repository, FakeCommandDispatcher(repository))
    assert repository.value is not None
    with pytest.raises(InvalidAction):
        await service.complete(
            triage,
            repository.value.record.id,
            progress_request(),
        )
