"""Pending Customer account requests kept outside the active identity table."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import UTC_TS, Base, TimestampMixin, _enum


class AccountRequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AccountRequest(TimestampMixin, Base):
    __tablename__ = "account_requests"

    display_name: Mapped[str] = mapped_column(String(120))
    contact_email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[AccountRequestStatus] = mapped_column(
        _enum(AccountRequestStatus, "account_request_status"),
        default=AccountRequestStatus.PENDING,
        server_default=AccountRequestStatus.PENDING.value,
        index=True,
    )
    decision_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
