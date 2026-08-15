"""Legacy plain-text deliverable persistence kept for completed MVP records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mist_service.model_enums import DeliverableStatus
from mist_service.orm_base import UTC_TS, Base, CreatedMixin, _enum


class Deliverable(CreatedMixin, Base):
    __tablename__ = "deliverables"
    __table_args__ = (UniqueConstraint("request_id", "version"),)

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    text: Mapped[str] = mapped_column(Text)
    author_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[DeliverableStatus] = mapped_column(
        _enum(DeliverableStatus, "deliverable_status"),
        default=DeliverableStatus.SUBMITTED,
    )
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    released_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    release_recipients: Mapped[list[str] | None] = mapped_column(JSON)
    approved_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    released_at: Mapped[datetime | None] = mapped_column(UTC_TS)
