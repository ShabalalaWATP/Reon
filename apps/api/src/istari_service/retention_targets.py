"""Legal-hold-aware retention conditions for persisted business records."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import String, exists
from sqlalchemy import cast as sql_cast
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from istari_service.account_request_models import AccountRequest, AccountRequestStatus
from istari_service.action_notification_models import NotificationEvent
from istari_service.clarification_models import ClarificationStatus, ClarificationThread
from istari_service.compliance_models import LegalHold, SecurityEvent
from istari_service.feedback_model import Feedback
from istari_service.models import Base, ServiceRequest
from istari_service.product_models import ProductAccessEvent, ProductPackage
from istari_service.team_models import TeamActivityEvent

type RetentionTarget = tuple[
    type[Base], ColumnElement[bool], InstrumentedAttribute[UUID]
]


def not_held(
    target_type: str,
    id_column: InstrumentedAttribute[UUID],
) -> ColumnElement[bool]:
    return ~exists().where(
        LegalHold.target_type == target_type,
        LegalHold.target_id == sql_cast(id_column, String),
        LegalHold.released_at.is_(None),
    )


def content_conditions(policy: object, now: datetime) -> dict[str, RetentionTarget]:
    def cutoff(attribute: str) -> datetime:
        return now - timedelta(days=int(getattr(policy, attribute)))

    return {
        "account_requests": (
            AccountRequest,
            (AccountRequest.status != AccountRequestStatus.PENDING)
            & (AccountRequest.reviewed_at <= cutoff("account_request_days"))
            & not_held("ACCOUNT_REQUEST", AccountRequest.id),
            AccountRequest.id,
        ),
        "completed_requests": (
            ServiceRequest,
            ServiceRequest.status.in_(
                ("COMPLETED", "CLOSED_NOT_PROGRESSED", "CANCELLED")
            )
            & (ServiceRequest.updated_at <= cutoff("completed_request_days"))
            & not_held("REQUEST", ServiceRequest.id),
            ServiceRequest.id,
        ),
        "activity_events": (
            TeamActivityEvent,
            (TeamActivityEvent.created_at <= cutoff("activity_days"))
            & not_held("ACTIVITY", TeamActivityEvent.id),
            TeamActivityEvent.id,
        ),
        "feedback": (
            Feedback,
            (Feedback.created_at <= cutoff("feedback_days"))
            & not_held("FEEDBACK", Feedback.id),
            Feedback.id,
        ),
        "clarifications": (
            ClarificationThread,
            (ClarificationThread.status != ClarificationStatus.OPEN)
            & (ClarificationThread.closed_at <= cutoff("clarification_days"))
            & not_held("CLARIFICATION", ClarificationThread.id),
            ClarificationThread.id,
        ),
        "notifications": (
            NotificationEvent,
            (NotificationEvent.occurred_at <= cutoff("notification_days"))
            & not_held("NOTIFICATION", NotificationEvent.id),
            NotificationEvent.id,
        ),
        "products": (
            ProductPackage,
            (ProductPackage.updated_at <= cutoff("product_days"))
            & not_held("PRODUCT", ProductPackage.id),
            ProductPackage.id,
        ),
        "access_events": (
            ProductAccessEvent,
            (ProductAccessEvent.created_at <= cutoff("access_event_days"))
            & not_held("ACCESS_EVENT", ProductAccessEvent.id),
            ProductAccessEvent.id,
        ),
        "security_events": (
            SecurityEvent,
            (SecurityEvent.created_at <= cutoff("security_event_days"))
            & not_held("SECURITY_EVENT", SecurityEvent.id),
            SecurityEvent.id,
        ),
    }
