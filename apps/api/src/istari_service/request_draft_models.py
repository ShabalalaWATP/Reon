"""Persistence model for private, incomplete Customer drafts."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from istari_service.models import Base, TimestampMixin

if TYPE_CHECKING:
    from istari_service.models import User


class RequestDraft(TimestampMixin, Base):
    __tablename__ = "request_drafts"

    requester_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(160))
    service_category: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    desired_outcome: Mapped[str | None] = mapped_column(Text)
    background_context: Mapped[str | None] = mapped_column(Text)
    required_by: Mapped[date | None] = mapped_column(Date)
    required_by_reason: Mapped[str | None] = mapped_column(Text)
    preferred_deliverable_type: Mapped[str | None] = mapped_column(String(80))
    success_criteria: Mapped[str | None] = mapped_column(Text)
    requesting_business_area: Mapped[str | None] = mapped_column(String(120))
    intended_recipients: Mapped[list[str] | None] = mapped_column(JSON)
    sensitivity: Mapped[str | None] = mapped_column(String(20))
    handling_instructions: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
