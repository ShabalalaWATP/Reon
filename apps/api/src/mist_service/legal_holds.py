"""Authorised legal-hold lifecycle kept separate from ordinary application roles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.account_request_models import AccountRequest
from mist_service.action_notification_models import NotificationEvent
from mist_service.board_models import WorkPackageActivity
from mist_service.clarification_models import ClarificationThread
from mist_service.compliance_models import LegalHold, SecurityEvent
from mist_service.feedback_model import Feedback
from mist_service.models import ServiceRequest, User
from mist_service.product_models import ProductAccessEvent, ProductPackage
from mist_service.retention_lock import acquire_retention_lock
from mist_service.team_models import TeamActivityEvent

LEGAL_HOLD_AUTHORITY = "LEGAL_HOLD_ADMIN"
LEGAL_HOLD_TARGETS = {
    "ACCOUNT_REQUEST": AccountRequest,
    "ACCESS_EVENT": ProductAccessEvent,
    "CLARIFICATION": ClarificationThread,
    "FEEDBACK": Feedback,
    "IDENTITY": User,
    "NOTIFICATION": NotificationEvent,
    "PRODUCT": ProductPackage,
    "REQUEST": ServiceRequest,
    "SECURITY_EVENT": SecurityEvent,
}


class LegalHoldService:
    def __init__(self, session: AsyncSession, *, subject: str, authority: str) -> None:
        if not subject.strip() or len(subject) > 160:
            raise ValueError("a bounded legal-hold identity is required")
        if authority != LEGAL_HOLD_AUTHORITY:
            raise ValueError("legal-hold authority is required")
        self._session = session
        self._subject = subject

    async def apply(
        self, target_type: str, target_id: UUID | str, reason_code: str
    ) -> LegalHold:
        canonical_id = _canonical_uuid(target_id)
        _validate(target_type, str(canonical_id), reason_code)
        await acquire_retention_lock(self._session)
        models = (
            (TeamActivityEvent, WorkPackageActivity)
            if target_type == "ACTIVITY"
            else (LEGAL_HOLD_TARGETS[target_type],)
        )
        found = False
        for model in models:
            row = await self._session.scalar(
                select(model).where(cast(Any, model).id == canonical_id)
            )
            found = found or row is not None
        if not found:
            raise LookupError("legal-hold target was not found")
        hold = LegalHold(
            target_type=target_type,
            target_id=str(canonical_id),
            reason_code=reason_code,
            authorised_by=self._subject,
        )
        self._session.add(hold)
        await self._session.flush()
        return hold

    async def release(self, target_type: str, target_id: UUID | str) -> LegalHold:
        canonical_id = _canonical_uuid(target_id)
        hold = await self._session.scalar(
            select(LegalHold)
            .where(
                LegalHold.target_type == target_type,
                LegalHold.target_id == str(canonical_id),
                LegalHold.released_at.is_(None),
            )
            .with_for_update()
        )
        if hold is None:
            raise LookupError("active legal hold was not found")
        hold.released_at = datetime.now(UTC)
        hold.released_by = self._subject
        await self._session.flush()
        return hold


def _validate(target_type: str, target_id: str, reason_code: str) -> None:
    if target_type != "ACTIVITY" and target_type not in LEGAL_HOLD_TARGETS:
        raise ValueError("legal-hold target type is invalid")
    for label, value, maximum in (
        ("target type", target_type, 40),
        ("target ID", target_id, 64),
        ("reason code", reason_code, 80),
    ):
        if not value or len(value) > maximum:
            raise ValueError(f"legal-hold {label} is invalid")


def _canonical_uuid(value: UUID | str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(value)
    except (TypeError, ValueError) as error:
        raise ValueError("legal-hold target ID is invalid") from error
