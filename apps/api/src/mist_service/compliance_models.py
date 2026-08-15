"""Content-free security evidence and legal-hold persistence."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, event, inspect, text
from sqlalchemy.orm import Mapped, mapped_column

from mist_service.models import UTC_TS, Base, CreatedMixin


class SecurityOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    EXPIRED = "EXPIRED"


class SecurityEvent(CreatedMixin, Base):
    """Attributable evidence which deliberately excludes submitted content."""

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_type_created", "event_type", "created_at"),
        CheckConstraint("length(event_type) > 0", name="security_event_type_present"),
    )

    event_type: Mapped[str] = mapped_column(String(80), index=True)
    outcome: Mapped[str] = mapped_column(String(20), index=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    subject_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    reason_code: Mapped[str] = mapped_column(String(80))
    correlation_id: Mapped[str | None] = mapped_column(String(80), index=True)
    request_method: Mapped[str | None] = mapped_column(String(10))
    route_template: Mapped[str | None] = mapped_column(String(160))
    deduplication_key: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True
    )


class LegalHold(CreatedMixin, Base):
    """Authorised suspension of disposal for one identity or business object."""

    __tablename__ = "legal_holds"
    __table_args__ = (
        Index(
            "uq_legal_holds_active_target",
            "target_type",
            "target_id",
            unique=True,
            sqlite_where=text("released_at IS NULL"),
            postgresql_where=text("released_at IS NULL"),
        ),
    )

    target_type: Mapped[str] = mapped_column(String(40), index=True)
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    reason_code: Mapped[str] = mapped_column(String(80))
    authorised_by: Mapped[str] = mapped_column(String(160))
    released_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    released_by: Mapped[str | None] = mapped_column(String(160))


def _reject_mutation(_mapper: Any, _connection: Any, _target: Any) -> None:
    raise ValueError("security evidence is append-only")


event.listen(SecurityEvent, "before_update", _reject_mutation)
event.listen(SecurityEvent, "before_delete", _reject_mutation)


def _protect_hold(_mapper: Any, _connection: Any, target: LegalHold) -> None:
    state = inspect(target)
    immutable = ("target_type", "target_id", "reason_code", "authorised_by")
    if any(state.attrs[field].history.has_changes() for field in immutable):
        raise ValueError("legal-hold authority and target are immutable")
    released_at = state.attrs.released_at.history
    released_by = state.attrs.released_by.history
    if released_at.has_changes() != released_by.has_changes():
        raise ValueError("legal-hold release fields must change together")
    if released_at.has_changes() and any(
        value is not None for value in released_at.deleted
    ):
        raise ValueError("legal-hold release is immutable")
    if released_by.has_changes() and any(
        value is not None for value in released_by.deleted
    ):
        raise ValueError("legal-hold release authority is immutable")
    if released_at.has_changes() and (
        target.released_at is None or not target.released_by
    ):
        raise ValueError("legal-hold release requires attributable evidence")


event.listen(LegalHold, "before_update", _protect_hold)
event.listen(LegalHold, "before_delete", _reject_mutation)
