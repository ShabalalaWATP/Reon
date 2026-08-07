"""Pure validation and event-catalogue branch coverage."""

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from istari_service.errors import InvalidAction
from istari_service.models import RequestEvent, RequestStatus
from istari_service.notification_catalog import render_subject
from istari_service.repositories.notifications import _state_filter
from istari_service.repositories.projection_pagination import (
    InvalidProjectionQuery,
    decode_cursor,
)
from istari_service.request_notification_projection import notification_spec
from istari_service.schemas.actions import (
    ActionColumn,
    ActionFilters,
    NotificationFilterState,
    NotificationPreferenceUpdate,
    NotificationStateAction,
    NotificationStateCommand,
    NotificationStateTarget,
    SavedActionViewCommand,
)
from istari_service.services.notification_service import _event_types, _validate_dates


@pytest.mark.parametrize(
    ("raw", "prior", "expected"),
    [
        ("workflow_withdraw", None, "REQUEST_WITHDRAWN"),
        ("product_withdrawn", None, "PRODUCT_WITHDRAWN"),
        ("workflow_close", None, "REQUEST_CLOSED"),
        ("workflow_hold", None, "REQUEST_HELD"),
        ("workflow_request_information", None, "CLARIFICATION_REQUESTED"),
        ("workflow_provide_information", None, "CLARIFICATION_ANSWERED"),
        ("workflow_submit", None, "MANAGER_REVIEW_REQUESTED"),
        ("workflow_approve", RequestStatus.LEAD_REVIEW, "MANAGER_REVIEW_APPROVED"),
        ("workflow_approve", RequestStatus.QUALITY_REVIEW, "QC_REVIEW_APPROVED"),
        (
            "workflow_changes_required",
            RequestStatus.LEAD_REVIEW,
            "MANAGER_REVIEW_RETURNED",
        ),
        (
            "workflow_changes_required",
            RequestStatus.QUALITY_REVIEW,
            "QC_REVIEW_RETURNED",
        ),
        ("workflow_release", None, "PRODUCT_DISSEMINATED"),
        ("feedback_submitted", None, "FEEDBACK_RECEIVED"),
        ("workflow_allocate", None, "TASK_ASSIGNED"),
        ("unrelated_event", None, None),
    ],
)
def test_notification_event_catalogue_mapping(
    raw: str, prior: RequestStatus | None, expected: str | None
) -> None:
    spec = notification_spec(RequestEvent(type=raw, prior_status=prior))
    assert (spec[0] if spec else None) == expected


def test_query_and_schema_validation_edges() -> None:
    with pytest.raises(InvalidAction):
        render_subject("UNKNOWN", "SR-1")
    naive = datetime.now(UTC).replace(tzinfo=None)
    with pytest.raises(InvalidProjectionQuery):
        _validate_dates(naive, None)
    with pytest.raises(InvalidProjectionQuery):
        _validate_dates(None, naive)
    now = datetime.now(UTC)
    with pytest.raises(InvalidProjectionQuery):
        _validate_dates(now, now - timedelta(days=1))
    with pytest.raises(InvalidProjectionQuery):
        _event_types(["unknown"])
    _state_filter(
        [
            NotificationFilterState.UNREAD,
            NotificationFilterState.READ,
            NotificationFilterState.ARCHIVED,
            NotificationFilterState.ACTION_COMPLETED,
        ]
    )
    _state_filter([NotificationFilterState.READ])
    naive_cursor = base64.urlsafe_b64encode(
        json.dumps([naive.isoformat(), str(uuid4())]).encode()
    ).decode()
    with pytest.raises(InvalidProjectionQuery):
        decode_cursor(naive_cursor, message="Invalid cursor.")
    target = NotificationStateTarget(id=uuid4(), expected_version=1)
    with pytest.raises(ValidationError):
        NotificationStateCommand(
            action=NotificationStateAction.MARK_READ, targets=[target, target]
        )
    with pytest.raises(ValidationError):
        NotificationPreferenceUpdate(
            enabled=True, reminder_days=[91], expected_version=0
        )
    with pytest.raises(ValidationError):
        NotificationPreferenceUpdate(
            enabled=True, reminder_days=[1, 7], expected_version=0
        )
    with pytest.raises(ValidationError):
        ActionFilters(action_types=[""])
    with pytest.raises(ValidationError):
        SavedActionViewCommand(
            name="View",
            filters=ActionFilters(),
            visible_columns=[ActionColumn.REFERENCE, ActionColumn.REFERENCE],
        )
