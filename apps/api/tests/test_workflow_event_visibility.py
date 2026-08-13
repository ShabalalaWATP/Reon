"""Customer workflow history excludes staff-authored notes and reasons."""

import pytest

from istari_service.request_event_audience import RequestEventAudience
from istari_service.workflow.types import WorkflowAction
from istari_service.workflow_event_visibility import work_event_audience


@pytest.mark.parametrize(
    "action",
    [WorkflowAction.SEND_TO_ALLOCATION, WorkflowAction.ASSIGN],
)
def test_staff_text_workflow_actions_are_not_customer_visible(
    action: WorkflowAction,
) -> None:
    assert work_event_audience(action) is RequestEventAudience.STAFF_ONLY


@pytest.mark.parametrize(
    "action",
    [
        WorkflowAction.PROGRESS,
        WorkflowAction.ALLOCATE,
        WorkflowAction.SUBMIT,
        WorkflowAction.APPROVE,
        WorkflowAction.RELEASE,
    ],
)
def test_safe_lifecycle_actions_remain_customer_visible(action: WorkflowAction) -> None:
    assert work_event_audience(action) is RequestEventAudience.CUSTOMER_AND_STAFF
