"""Customer feedback persistence kept outside the core workflow model file."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from mist_service.orm_base import UUID_TYPE, Base, CreatedMixin


class Feedback(CreatedMixin, Base):
    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),)

    request_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("service_requests.id"),
        unique=True,
        index=True,
    )
    requester_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("users.id"),
    )
    submission_key: Mapped[UUID | None] = mapped_column(
        UUID_TYPE,
        unique=True,
        index=True,
    )
    rating: Mapped[int] = mapped_column(Integer)
    comments: Mapped[str] = mapped_column(Text)
