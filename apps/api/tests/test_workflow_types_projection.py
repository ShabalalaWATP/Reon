"""Unit coverage for workflow values and the BPMN projection matrix."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import pytest

from mist_service.models import RequestStatus
from mist_service.workflow.errors import (
    InvalidWorkflowTransition,
    UnknownWorkflowElement,
    WorkflowRequestRejected,
)
from mist_service.workflow.projection import (
    ACTION_RESULT_STATUSES,
    DECISION_VARIABLES_BY_ELEMENT,
    ELEMENT_IDS_BY_STATUS,
    ELEMENT_STATUSES,
    decision_variable_for_element,
    element_id_for_status,
    ensure_action_matches_element,
    status_after_action,
    status_for_element,
)
from mist_service.workflow.types import (
    ActiveTaskQuery,
    ClaimTaskCommand,
    CompleteTaskCommand,
    DeliveryTeamId,
    StartedProcess,
    StartedProcessQuery,
    StartProcessCommand,
    WorkflowAction,
    WorkflowTask,
    WorkflowTaskState,
)

REQUEST_ID = UUID("00000000-0000-4000-8000-000000000001")
REQUESTER_ID = UUID("00000000-0000-4000-8000-000000000002")
SPECIALIST_ID = UUID("00000000-0000-4000-8000-000000000003")


def start_command(**changes: object) -> StartProcessCommand:
    values: dict[str, object] = {
        "process_definition_id": "service_request",
        "request_id": REQUEST_ID,
        "requester_id": REQUESTER_ID,
    }
    values.update(changes)
    return StartProcessCommand(**values)  # type: ignore[arg-type]


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
    ("factory", "error", "message"),
    [
        (lambda: start_command(process_definition_id=" "), ValueError, "not be empty"),
        (lambda: start_command(request_id="bad"), TypeError, "request_id"),
        (lambda: start_command(requester_id="bad"), TypeError, "requester_id"),
        (lambda: start_command(process_definition_version=0), ValueError, "positive"),
        (lambda: start_command(tenant_id=" "), ValueError, "tenant_id"),
        (
            lambda: StartedProcess("", "definition", "service_request", 1, "id"),
            ValueError,
            "identifiers",
        ),
        (
            lambda: StartedProcess("process", "definition", "service_request", 0, "id"),
            ValueError,
            "version",
        ),
        (lambda: StartedProcessQuery("", REQUEST_ID), ValueError, "not be empty"),
        (lambda: StartedProcessQuery("definition", "bad"), TypeError, "request_id"),
        (
            lambda: StartedProcessQuery("definition", REQUEST_ID, 0),
            ValueError,
            "positive",
        ),
        (
            lambda: StartedProcessQuery("definition", REQUEST_ID, tenant_id=" "),
            ValueError,
            "tenant_id",
        ),
        (lambda: ActiveTaskQuery(""), ValueError, "process_instance_key"),
        (lambda: ActiveTaskQuery("process", " "), ValueError, "expected_element_id"),
        (
            lambda: WorkflowTask("", "process", "element", WorkflowTaskState.CREATED),
            ValueError,
            "identifiers",
        ),
        (
            lambda: WorkflowTask("task", "process", "element", "CREATED"),
            TypeError,
            "WorkflowTaskState",
        ),
        (
            lambda: WorkflowTask(
                "task", "process", "element", WorkflowTaskState.CREATED, " "
            ),
            ValueError,
            "assignee",
        ),
        (lambda: complete_command(task_key=""), ValueError, "task_key"),
        (
            lambda: complete_command(process_instance_key=""),
            ValueError,
            "process_instance_key",
        ),
        (
            lambda: complete_command(expected_element_id=""),
            ValueError,
            "expected_element_id",
        ),
        (lambda: complete_command(action="progress"), TypeError, "WorkflowAction"),
        (
            lambda: complete_command(delivery_team_id="team"),
            TypeError,
            "DeliveryTeamId",
        ),
        (
            lambda: complete_command(specialist_id="specialist"),
            TypeError,
            "UUID",
        ),
        (
            lambda: complete_command(action=WorkflowAction.ALLOCATE),
            ValueError,
            "allocate requires",
        ),
        (
            lambda: complete_command(
                action=WorkflowAction.ALLOCATE,
                delivery_team_id=DeliveryTeamId.DELIVERY_TEAM_A,
                specialist_id=SPECIALIST_ID,
            ),
            ValueError,
            "allocate requires",
        ),
        (
            lambda: complete_command(action=WorkflowAction.ASSIGN),
            ValueError,
            "assign requires",
        ),
        (
            lambda: complete_command(
                action=WorkflowAction.ASSIGN,
                delivery_team_id=DeliveryTeamId.DELIVERY_TEAM_A,
                specialist_id=SPECIALIST_ID,
            ),
            ValueError,
            "assign requires",
        ),
        (
            lambda: complete_command(delivery_team_id=DeliveryTeamId.DELIVERY_TEAM_A),
            ValueError,
            "routing identifiers",
        ),
        (lambda: ClaimTaskCommand("", REQUESTER_ID), ValueError, "task_key"),
        (lambda: ClaimTaskCommand("task", "bad"), TypeError, "assignee_id"),
    ],
)
def test_value_objects_reject_invalid_inputs_safely(
    factory: Callable[[], object],
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        factory()


def test_value_objects_accept_complete_valid_forms() -> None:
    command = start_command(process_definition_version=2, tenant_id="tenant-a")
    query = StartedProcessQuery.from_start(command)
    started = StartedProcess("process", "definition", "service_request", 2, "business")
    task_query = ActiveTaskQuery("process", "intake_review")
    task = WorkflowTask(
        "task", "process", "intake_review", WorkflowTaskState.CREATED, "user"
    )
    allocation = complete_command(
        expected_element_id="allocation_review",
        action=WorkflowAction.ALLOCATE,
        delivery_team_id=DeliveryTeamId.DELIVERY_TEAM_A,
    )
    assignment = complete_command(
        expected_element_id="delivery_planning",
        action=WorkflowAction.ASSIGN,
        specialist_id=SPECIALIST_ID,
    )
    claim = ClaimTaskCommand("task", REQUESTER_ID)

    assert query == StartedProcessQuery("service_request", REQUEST_ID, 2, "tenant-a")
    assert started.business_id == "business"
    assert task_query.expected_element_id == "intake_review"
    assert task.assignee == "user"
    assert allocation.delivery_team_id is DeliveryTeamId.DELIVERY_TEAM_A
    assert assignment.specialist_id == SPECIALIST_ID
    assert claim.assignee_id == REQUESTER_ID


TRANSITIONS = (
    (
        RequestStatus.TRIAGE_REVIEW,
        WorkflowAction.REQUEST_INFORMATION,
        RequestStatus.INFORMATION_REQUIRED,
    ),
    (
        RequestStatus.TRIAGE_REVIEW,
        WorkflowAction.PROGRESS,
        RequestStatus.COORDINATION_REVIEW,
    ),
    (
        RequestStatus.TRIAGE_REVIEW,
        WorkflowAction.CLOSE,
        RequestStatus.CLOSED_NOT_PROGRESSED,
    ),
    (
        RequestStatus.INFORMATION_REQUIRED,
        WorkflowAction.PROVIDE_INFORMATION,
        RequestStatus.TRIAGE_REVIEW,
    ),
    (
        RequestStatus.INFORMATION_REQUIRED,
        WorkflowAction.WITHDRAW,
        RequestStatus.CANCELLED,
    ),
    (
        RequestStatus.COORDINATION_REVIEW,
        WorkflowAction.SEND_TO_ALLOCATION,
        RequestStatus.ALLOCATION_REVIEW,
    ),
    (
        RequestStatus.COORDINATION_REVIEW,
        WorkflowAction.RETURN_TO_TRIAGE,
        RequestStatus.TRIAGE_REVIEW,
    ),
    (RequestStatus.COORDINATION_REVIEW, WorkflowAction.HOLD, RequestStatus.ON_HOLD),
    (
        RequestStatus.COORDINATION_REVIEW,
        WorkflowAction.CLOSE,
        RequestStatus.CLOSED_NOT_PROGRESSED,
    ),
    (RequestStatus.ON_HOLD, WorkflowAction.RESUME, RequestStatus.COORDINATION_REVIEW),
    (RequestStatus.ON_HOLD, WorkflowAction.CLOSE, RequestStatus.CLOSED_NOT_PROGRESSED),
    (
        RequestStatus.ALLOCATION_REVIEW,
        WorkflowAction.ALLOCATE,
        RequestStatus.DELIVERY_PLANNING,
    ),
    (
        RequestStatus.ALLOCATION_REVIEW,
        WorkflowAction.RETURN_TO_COORDINATION,
        RequestStatus.COORDINATION_REVIEW,
    ),
    (RequestStatus.DELIVERY_PLANNING, WorkflowAction.ASSIGN, RequestStatus.IN_PROGRESS),
    (
        RequestStatus.DELIVERY_PLANNING,
        WorkflowAction.RETURN_FOR_REALLOCATION,
        RequestStatus.ALLOCATION_REVIEW,
    ),
    (RequestStatus.IN_PROGRESS, WorkflowAction.SUBMIT, RequestStatus.LEAD_REVIEW),
    (RequestStatus.REWORK_REQUIRED, WorkflowAction.SUBMIT, RequestStatus.LEAD_REVIEW),
    (RequestStatus.LEAD_REVIEW, WorkflowAction.APPROVE, RequestStatus.QUALITY_REVIEW),
    (
        RequestStatus.LEAD_REVIEW,
        WorkflowAction.CHANGES_REQUIRED,
        RequestStatus.REWORK_REQUIRED,
    ),
    (
        RequestStatus.QUALITY_REVIEW,
        WorkflowAction.APPROVE,
        RequestStatus.READY_FOR_RELEASE,
    ),
    (
        RequestStatus.QUALITY_REVIEW,
        WorkflowAction.CHANGES_REQUIRED,
        RequestStatus.REWORK_REQUIRED,
    ),
    (RequestStatus.READY_FOR_RELEASE, WorkflowAction.RELEASE, RequestStatus.COMPLETED),
)


@pytest.mark.parametrize(("status", "action", "result"), TRANSITIONS)
def test_transition_matrix_is_explicit_and_complete(
    status: RequestStatus,
    action: WorkflowAction,
    result: RequestStatus,
) -> None:
    assert status_after_action(status, action) is result
    assert ACTION_RESULT_STATUSES[(status, action)] is result


def test_element_and_decision_mappings_are_exact() -> None:
    assert len(ELEMENT_STATUSES) == 11
    assert len(ELEMENT_IDS_BY_STATUS) == 12
    assert len(DECISION_VARIABLES_BY_ELEMENT) == 10
    for element_id, status in ELEMENT_STATUSES.items():
        assert status_for_element(element_id) is status
        assert element_id_for_status(status) == element_id
        assert decision_variable_for_element(element_id) == (
            DECISION_VARIABLES_BY_ELEMENT.get(element_id)
        )
    assert element_id_for_status(RequestStatus.ROUTING_PENDING) is None
    assert element_id_for_status(RequestStatus.REWORK_REQUIRED) == "delivery_work"


def test_projection_rejects_unknown_elements_and_transitions() -> None:
    with pytest.raises(UnknownWorkflowElement, match="mystery"):
        status_for_element("mystery")
    with pytest.raises(UnknownWorkflowElement):
        decision_variable_for_element("mystery")
    with pytest.raises(InvalidWorkflowTransition, match="release"):
        status_after_action(RequestStatus.TRIAGE_REVIEW, WorkflowAction.RELEASE)
    with pytest.raises(InvalidWorkflowTransition, match="allocation_review"):
        ensure_action_matches_element("allocation_review", WorkflowAction.PROGRESS)


def test_element_action_validation_handles_gateway_and_delivery_tasks() -> None:
    ensure_action_matches_element("intake_review", WorkflowAction.PROGRESS)
    ensure_action_matches_element("delivery_work", WorkflowAction.SUBMIT)
    ensure_action_matches_element("delivery_work", WorkflowAction.REQUEST_CLARIFICATION)
    with pytest.raises(InvalidWorkflowTransition, match="delivery_work"):
        ensure_action_matches_element("delivery_work", WorkflowAction.APPROVE)


def test_rejected_error_exposes_safe_operation_context() -> None:
    error = WorkflowRequestRejected("claim_task", 403)
    assert error.operation == "claim_task"
    assert error.status_code == 403
    assert str(error) == "workflow operation 'claim_task' returned HTTP 403"
