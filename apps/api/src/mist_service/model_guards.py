"""SQLAlchemy guards for immutable submitted content and audit records."""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, inspect

import mist_service.board_models as _board_models  # noqa: F401
import mist_service.calendar_models as _calendar_models  # noqa: F401
from mist_service.analytics_evolution_models import (
    AnalyticsExportAuditEvent,
    OperationalAnalyticsFact,
)
from mist_service.board_models import WorkPackageActivity
from mist_service.conversation_models import (
    RequestConversation,
    RequestConversationDelivery,
    RequestConversationMessage,
)
from mist_service.feedback_model import Feedback
from mist_service.models import ServiceRequest
from mist_service.operations_models import OperationalRun
from mist_service.request_event_models import RequestEvent
from mist_service.team_models import TeamActivityEvent


@event.listens_for(ServiceRequest, "before_update")
def _protect_form(_mapper: Any, _connection: Any, target: ServiceRequest) -> None:
    fields = (  # noqa: SIM905
        "title service_category description desired_outcome background_context "
        "required_by required_by_reason preferred_deliverable_type success_criteria "
        "question_to_answer subject_area_or_location coverage_start coverage_end "
        "customer_urgency supported_activity_or_decision constraints_or_caveats "
        "supporting_information sensitivity handling_instructions"
    ).split()
    state = inspect(target)
    if any(state.attrs[field].history.has_changes() for field in fields):
        raise ValueError("submitted request form fields are immutable")


def _reject_audit_mutation(_mapper: Any, _connection: Any, _target: Any) -> None:
    raise ValueError("audit records are append-only")


@event.listens_for(RequestConversationDelivery, "before_update")
def _protect_read_receipt(_mapper: Any, _connection: Any, target: Any) -> None:
    state = inspect(target)
    history = state.attrs.read_at.history
    if history.has_changes() and (
        history.deleted != [None] or len(history.added) != 1 or history.added[0] is None
    ):
        raise ValueError("conversation read receipts can only advance once")


for audit_type in (
    Feedback,
    RequestEvent,
    TeamActivityEvent,
    WorkPackageActivity,
    OperationalRun,
    OperationalAnalyticsFact,
    AnalyticsExportAuditEvent,
    RequestConversation,
    RequestConversationMessage,
):
    event.listen(audit_type, "before_update", _reject_audit_mutation)
    event.listen(audit_type, "before_delete", _reject_audit_mutation)

event.listen(RequestConversationDelivery, "before_delete", _reject_audit_mutation)
