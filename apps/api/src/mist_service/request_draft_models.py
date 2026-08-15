"""Persistence model for private, incomplete Customer drafts."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mist_service.models import Base, TimestampMixin

if TYPE_CHECKING:
    from mist_service.models import User


class RequestDraft(TimestampMixin, Base):
    __tablename__ = "request_drafts"
    __table_args__ = (
        Index(
            "ix_request_drafts_requester_updated_id",
            "requester_id",
            "updated_at",
            "id",
        ),
    )

    requester_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(160))
    service_category: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    question_to_answer: Mapped[str | None] = mapped_column(Text)
    desired_outcome: Mapped[str | None] = mapped_column(Text)
    background_context: Mapped[str | None] = mapped_column(Text)
    subject_area_or_location: Mapped[str | None] = mapped_column(Text)
    coverage_start: Mapped[date | None] = mapped_column(Date)
    coverage_end: Mapped[date | None] = mapped_column(Date)
    customer_urgency: Mapped[str | None] = mapped_column(String(20))
    supported_activity_or_decision: Mapped[str | None] = mapped_column(Text)
    required_by: Mapped[date | None] = mapped_column(Date)
    required_by_reason: Mapped[str | None] = mapped_column(Text)
    preferred_deliverable_type: Mapped[str | None] = mapped_column(String(80))
    success_criteria: Mapped[str | None] = mapped_column(Text)
    constraints_or_caveats: Mapped[str | None] = mapped_column(Text)
    supporting_information: Mapped[str | None] = mapped_column(Text)
    sensitivity: Mapped[str | None] = mapped_column(String(20))
    handling_instructions: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
