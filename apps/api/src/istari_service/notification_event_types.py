"""Safe notification event classification for request audit events."""

from __future__ import annotations

from istari_service.action_notification_models import NotificationEventGroup
from istari_service.models import RequestEvent, RequestStatus

DIRECT_NOTIFICATION_SPECS: dict[str, tuple[str, NotificationEventGroup]] = {
    "request_submitted": (
        "REQUEST_SUBMITTED",
        NotificationEventGroup.REQUEST_LIFECYCLE,
    ),
    "request_cancelled": (
        "REQUEST_CANCELLED",
        NotificationEventGroup.REQUEST_LIFECYCLE,
    ),
    "workflow_withdraw": (
        "REQUEST_WITHDRAWN",
        NotificationEventGroup.REQUEST_LIFECYCLE,
    ),
    "product_withdrawn": ("PRODUCT_WITHDRAWN", NotificationEventGroup.RELEASE),
    "workflow_close": ("REQUEST_CLOSED", NotificationEventGroup.REQUEST_LIFECYCLE),
    "workflow_hold": ("REQUEST_HELD", NotificationEventGroup.REQUEST_LIFECYCLE),
    "workflow_request_information": (
        "CLARIFICATION_REQUESTED",
        NotificationEventGroup.CLARIFICATION,
    ),
    "workflow_request_clarification": (
        "CLARIFICATION_REQUESTED",
        NotificationEventGroup.CLARIFICATION,
    ),
    "workflow_provide_information": (
        "CLARIFICATION_ANSWERED",
        NotificationEventGroup.CLARIFICATION,
    ),
    "workflow_provide_clarification": (
        "CLARIFICATION_ANSWERED",
        NotificationEventGroup.CLARIFICATION,
    ),
    "workflow_submit": ("MANAGER_REVIEW_REQUESTED", NotificationEventGroup.REVIEW),
    "product_package_submitted": (
        "MANAGER_REVIEW_REQUESTED",
        NotificationEventGroup.REVIEW,
    ),
    "workflow_release": ("PRODUCT_DISSEMINATED", NotificationEventGroup.RELEASE),
    "product_disseminated": ("PRODUCT_DISSEMINATED", NotificationEventGroup.RELEASE),
    "feedback_submitted": ("FEEDBACK_RECEIVED", NotificationEventGroup.FEEDBACK),
}

REVIEW_NOTIFICATION_SPECS: dict[str, tuple[str, str]] = {
    "workflow_approve": ("MANAGER_REVIEW_APPROVED", "QC_REVIEW_APPROVED"),
    "workflow_changes_required": (
        "MANAGER_REVIEW_RETURNED",
        "QC_REVIEW_RETURNED",
    ),
}


def notification_spec(
    event: RequestEvent,
) -> tuple[str, NotificationEventGroup] | None:
    raw = event.type.lower()
    direct = DIRECT_NOTIFICATION_SPECS.get(raw)
    if direct is not None:
        return direct
    review = REVIEW_NOTIFICATION_SPECS.get(raw)
    if review is not None:
        event_type = (
            review[0] if event.prior_status is RequestStatus.LEAD_REVIEW else review[1]
        )
        return event_type, NotificationEventGroup.REVIEW
    if raw.startswith("workflow_"):
        return "TASK_ASSIGNED", NotificationEventGroup.ASSIGNMENT
    return None
