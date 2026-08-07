"""Pure, explicit projection from BPMN position and human route results."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from istari_service.models import RequestStatus
from istari_service.workflow.errors import (
    InvalidWorkflowTransition,
    UnknownWorkflowElement,
)
from istari_service.workflow.types import WorkflowAction

INTAKE_REVIEW_ELEMENT_ID: Final = "intake_review"
REQUESTER_RESPONSE_ELEMENT_ID: Final = "requester_response"
COORDINATION_REVIEW_ELEMENT_ID: Final = "coordination_review"
ON_HOLD_ELEMENT_ID: Final = "on_hold"
ALLOCATION_REVIEW_ELEMENT_ID: Final = "allocation_review"
DELIVERY_PLANNING_ELEMENT_ID: Final = "delivery_planning"
DELIVERY_WORK_ELEMENT_ID: Final = "delivery_work"
CUSTOMER_CLARIFICATION_ELEMENT_ID: Final = "customer_clarification_response"
LEAD_REVIEW_ELEMENT_ID: Final = "lead_review"
QUALITY_REVIEW_ELEMENT_ID: Final = "quality_review"
RELEASE_ELEMENT_ID: Final = "release"
FIRST_TASK_RECONCILIATION_MESSAGE: Final = "The first work item is being reconciled."
NEXT_TASK_RECONCILIATION_MESSAGE: Final = "The next work item is being reconciled."
RECONCILIATION_MESSAGES: Final = frozenset(
    {FIRST_TASK_RECONCILIATION_MESSAGE, NEXT_TASK_RECONCILIATION_MESSAGE}
)

ELEMENT_STATUSES: Mapping[str, RequestStatus] = MappingProxyType(
    {
        INTAKE_REVIEW_ELEMENT_ID: RequestStatus.TRIAGE_REVIEW,
        REQUESTER_RESPONSE_ELEMENT_ID: RequestStatus.INFORMATION_REQUIRED,
        COORDINATION_REVIEW_ELEMENT_ID: RequestStatus.COORDINATION_REVIEW,
        ON_HOLD_ELEMENT_ID: RequestStatus.ON_HOLD,
        ALLOCATION_REVIEW_ELEMENT_ID: RequestStatus.ALLOCATION_REVIEW,
        DELIVERY_PLANNING_ELEMENT_ID: RequestStatus.DELIVERY_PLANNING,
        DELIVERY_WORK_ELEMENT_ID: RequestStatus.IN_PROGRESS,
        CUSTOMER_CLARIFICATION_ELEMENT_ID: (
            RequestStatus.CUSTOMER_INFORMATION_REQUIRED
        ),
        LEAD_REVIEW_ELEMENT_ID: RequestStatus.LEAD_REVIEW,
        QUALITY_REVIEW_ELEMENT_ID: RequestStatus.QUALITY_REVIEW,
        RELEASE_ELEMENT_ID: RequestStatus.READY_FOR_RELEASE,
    }
)

ELEMENT_IDS_BY_STATUS: Mapping[RequestStatus, str] = MappingProxyType(
    {
        RequestStatus.TRIAGE_REVIEW: INTAKE_REVIEW_ELEMENT_ID,
        RequestStatus.INFORMATION_REQUIRED: REQUESTER_RESPONSE_ELEMENT_ID,
        RequestStatus.COORDINATION_REVIEW: COORDINATION_REVIEW_ELEMENT_ID,
        RequestStatus.ON_HOLD: ON_HOLD_ELEMENT_ID,
        RequestStatus.ALLOCATION_REVIEW: ALLOCATION_REVIEW_ELEMENT_ID,
        RequestStatus.DELIVERY_PLANNING: DELIVERY_PLANNING_ELEMENT_ID,
        RequestStatus.IN_PROGRESS: DELIVERY_WORK_ELEMENT_ID,
        RequestStatus.REWORK_REQUIRED: DELIVERY_WORK_ELEMENT_ID,
        RequestStatus.CUSTOMER_INFORMATION_REQUIRED: (
            CUSTOMER_CLARIFICATION_ELEMENT_ID
        ),
        RequestStatus.LEAD_REVIEW: LEAD_REVIEW_ELEMENT_ID,
        RequestStatus.QUALITY_REVIEW: QUALITY_REVIEW_ELEMENT_ID,
        RequestStatus.READY_FOR_RELEASE: RELEASE_ELEMENT_ID,
    }
)

DECISION_VARIABLES_BY_ELEMENT: Mapping[str, str] = MappingProxyType(
    {
        INTAKE_REVIEW_ELEMENT_ID: "intakeDecision",
        REQUESTER_RESPONSE_ELEMENT_ID: "requesterDecision",
        COORDINATION_REVIEW_ELEMENT_ID: "coordinationDecision",
        ON_HOLD_ELEMENT_ID: "holdDecision",
        ALLOCATION_REVIEW_ELEMENT_ID: "allocationDecision",
        DELIVERY_PLANNING_ELEMENT_ID: "planningDecision",
        DELIVERY_WORK_ELEMENT_ID: "deliveryDecision",
        CUSTOMER_CLARIFICATION_ELEMENT_ID: "clarificationDecision",
        LEAD_REVIEW_ELEMENT_ID: "leadReviewDecision",
        QUALITY_REVIEW_ELEMENT_ID: "qualityDecision",
    }
)

ACTION_RESULT_STATUSES: Mapping[tuple[RequestStatus, WorkflowAction], RequestStatus] = (
    MappingProxyType(
        {
            (RequestStatus.TRIAGE_REVIEW, WorkflowAction.REQUEST_INFORMATION): (
                RequestStatus.INFORMATION_REQUIRED
            ),
            (RequestStatus.TRIAGE_REVIEW, WorkflowAction.PROGRESS): (
                RequestStatus.COORDINATION_REVIEW
            ),
            (RequestStatus.TRIAGE_REVIEW, WorkflowAction.CLOSE): (
                RequestStatus.CLOSED_NOT_PROGRESSED
            ),
            (RequestStatus.INFORMATION_REQUIRED, WorkflowAction.PROVIDE_INFORMATION): (
                RequestStatus.TRIAGE_REVIEW
            ),
            (RequestStatus.INFORMATION_REQUIRED, WorkflowAction.WITHDRAW): (
                RequestStatus.CANCELLED
            ),
            (RequestStatus.COORDINATION_REVIEW, WorkflowAction.SEND_TO_ALLOCATION): (
                RequestStatus.ALLOCATION_REVIEW
            ),
            (RequestStatus.COORDINATION_REVIEW, WorkflowAction.RETURN_TO_TRIAGE): (
                RequestStatus.TRIAGE_REVIEW
            ),
            (RequestStatus.COORDINATION_REVIEW, WorkflowAction.HOLD): (
                RequestStatus.ON_HOLD
            ),
            (RequestStatus.COORDINATION_REVIEW, WorkflowAction.CLOSE): (
                RequestStatus.CLOSED_NOT_PROGRESSED
            ),
            (RequestStatus.ON_HOLD, WorkflowAction.RESUME): (
                RequestStatus.COORDINATION_REVIEW
            ),
            (RequestStatus.ON_HOLD, WorkflowAction.CLOSE): (
                RequestStatus.CLOSED_NOT_PROGRESSED
            ),
            (RequestStatus.ALLOCATION_REVIEW, WorkflowAction.ALLOCATE): (
                RequestStatus.DELIVERY_PLANNING
            ),
            (RequestStatus.ALLOCATION_REVIEW, WorkflowAction.RETURN_TO_COORDINATION): (
                RequestStatus.COORDINATION_REVIEW
            ),
            (RequestStatus.DELIVERY_PLANNING, WorkflowAction.ASSIGN): (
                RequestStatus.IN_PROGRESS
            ),
            (
                RequestStatus.DELIVERY_PLANNING,
                WorkflowAction.RETURN_FOR_REALLOCATION,
            ): RequestStatus.ALLOCATION_REVIEW,
            (
                RequestStatus.IN_PROGRESS,
                WorkflowAction.SUBMIT,
            ): RequestStatus.LEAD_REVIEW,
            (RequestStatus.REWORK_REQUIRED, WorkflowAction.SUBMIT): (
                RequestStatus.LEAD_REVIEW
            ),
            (
                RequestStatus.IN_PROGRESS,
                WorkflowAction.REQUEST_CLARIFICATION,
            ): RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
            (
                RequestStatus.REWORK_REQUIRED,
                WorkflowAction.REQUEST_CLARIFICATION,
            ): RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
            (
                RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
                WorkflowAction.PROVIDE_CLARIFICATION,
            ): RequestStatus.IN_PROGRESS,
            (
                RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
                WorkflowAction.WITHDRAW,
            ): RequestStatus.CANCELLED,
            (RequestStatus.LEAD_REVIEW, WorkflowAction.APPROVE): (
                RequestStatus.QUALITY_REVIEW
            ),
            (RequestStatus.LEAD_REVIEW, WorkflowAction.CHANGES_REQUIRED): (
                RequestStatus.REWORK_REQUIRED
            ),
            (RequestStatus.QUALITY_REVIEW, WorkflowAction.APPROVE): (
                RequestStatus.READY_FOR_RELEASE
            ),
            (RequestStatus.QUALITY_REVIEW, WorkflowAction.CHANGES_REQUIRED): (
                RequestStatus.REWORK_REQUIRED
            ),
            (RequestStatus.READY_FOR_RELEASE, WorkflowAction.RELEASE): (
                RequestStatus.COMPLETED
            ),
        }
    )
)


def status_for_element(element_id: str) -> RequestStatus:
    """Project a visible task element to its default application status."""

    try:
        return ELEMENT_STATUSES[element_id]
    except KeyError as exc:
        raise UnknownWorkflowElement(
            f"workflow element {element_id!r} has no status projection"
        ) from exc


def element_id_for_status(status: RequestStatus) -> str | None:
    """Return the expected active task, or ``None`` for non-task statuses."""

    return ELEMENT_IDS_BY_STATUS.get(status)


def decision_variable_for_element(element_id: str) -> str | None:
    """Return the one BPMN decision variable allowed for this task, if any."""

    status_for_element(element_id)
    return DECISION_VARIABLES_BY_ELEMENT.get(element_id)


def status_after_action(
    current_status: RequestStatus,
    action: WorkflowAction,
) -> RequestStatus:
    """Project one explicit human route result without inferring a decision."""

    try:
        return ACTION_RESULT_STATUSES[(current_status, action)]
    except KeyError as exc:
        raise InvalidWorkflowTransition(
            f"action {action.value!r} is invalid for {current_status.value!r}"
        ) from exc


def ensure_action_matches_element(element_id: str, action: WorkflowAction) -> None:
    """Reject actions that cannot originate from the supplied BPMN element."""

    status = status_for_element(element_id)
    if element_id == DELIVERY_WORK_ELEMENT_ID:
        if action in {
            WorkflowAction.SUBMIT,
            WorkflowAction.REQUEST_CLARIFICATION,
        }:
            return
    elif (status, action) in ACTION_RESULT_STATUSES:
        return
    raise InvalidWorkflowTransition(
        f"action {action.value!r} is invalid for element {element_id!r}"
    )
