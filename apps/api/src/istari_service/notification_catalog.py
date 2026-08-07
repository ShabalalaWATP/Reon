"""Server-owned, content-free notification event catalogue."""

from __future__ import annotations

import re

from istari_service.errors import InvalidAction

REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,63}")
EVENT_LABELS = {
    "REQUEST_SUBMITTED": "request submitted",
    "REQUEST_WITHDRAWN": "request withdrawn",
    "REQUEST_CLOSED": "request closed",
    "REQUEST_HELD": "request held",
    "TASK_ASSIGNED": "action assigned",
    "TASK_REASSIGNED": "action reassigned",
    "TASK_RETURNED": "action returned",
    "CLARIFICATION_REQUESTED": "clarification requested",
    "CLARIFICATION_ANSWERED": "clarification answered",
    "CLARIFICATION_OVERDUE": "clarification overdue",
    "CLARIFICATION_WITHDRAWN": "clarification withdrawn",
    "REQUIRED_DATE_APPROACHING": "required date approaching",
    "REQUIRED_DATE_PASSED": "required date passed",
    "MANAGER_REVIEW_REQUESTED": "Manager review requested",
    "MANAGER_REVIEW_APPROVED": "Manager review approved",
    "MANAGER_REVIEW_RETURNED": "Manager review returned",
    "QC_REVIEW_REQUESTED": "quality review requested",
    "QC_REVIEW_APPROVED": "quality review approved",
    "QC_REVIEW_RETURNED": "quality review returned",
    "PRODUCT_DISSEMINATED": "product disseminated",
    "PRODUCT_REPLACED": "product replaced",
    "PRODUCT_WITHDRAWN": "product withdrawn",
    "FEEDBACK_REQUESTED": "feedback requested",
    "FEEDBACK_RECEIVED": "feedback received",
    "TEAM_MEMBERSHIP_CHANGED": "team membership changed",
    "CAPACITY_COMMITMENT_CHANGED": "capacity commitment changed",
    "CONFIGURATION_AWAITING_REVIEW": "configuration awaiting review",
    "CONFIGURATION_ACTIVATED": "configuration activated",
    "CONFIGURATION_REJECTED": "configuration rejected",
    "CONFIGURATION_SUPERSEDED": "configuration superseded",
    "ACCOUNT_SECURITY_CHANGED": "account security changed",
}


def render_subject(event_type: str, reference: str) -> tuple[str, str]:
    normalised = event_type.strip().upper()
    label = EVENT_LABELS.get(normalised)
    cleaned_reference = reference.strip()
    if label is None or REFERENCE.fullmatch(cleaned_reference) is None:
        raise InvalidAction("The notification event metadata is invalid.")
    return normalised, f"{cleaned_reference}: {label}."
