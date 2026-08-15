"""Customer visibility classification for workflow lifecycle events."""

from mist_service.request_event_audience import RequestEventAudience
from mist_service.workflow.types import WorkflowAction

PUBLIC_WORKFLOW_ACTIONS = frozenset(
    {
        WorkflowAction.PROGRESS,
        WorkflowAction.ALLOCATE,
        WorkflowAction.SUBMIT,
        WorkflowAction.APPROVE,
        WorkflowAction.RELEASE,
    }
)


def work_event_audience(action: WorkflowAction) -> RequestEventAudience:
    """Expose only lifecycle actions whose messages contain no staff-authored text."""

    return (
        RequestEventAudience.CUSTOMER_AND_STAFF
        if action in PUBLIC_WORKFLOW_ACTIONS
        else RequestEventAudience.STAFF_ONLY
    )
