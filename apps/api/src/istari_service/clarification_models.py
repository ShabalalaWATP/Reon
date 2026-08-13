"""Append-only production clarification records and messages."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from istari_service.models import UTC_TS, Base, CreatedMixin, TimestampMixin

if TYPE_CHECKING:
    from istari_service.models import ServiceRequest, User


class ClarificationStatus(StrEnum):
    OPEN = "OPEN"
    ANSWERED = "ANSWERED"
    WITHDRAWN = "WITHDRAWN"


class ClarificationMessageKind(StrEnum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    WITHDRAWAL = "WITHDRAWAL"


class ClarificationThread(TimestampMixin, Base):
    __tablename__ = "clarification_threads"
    __table_args__ = (
        UniqueConstraint("request_id", "sequence"),
        CheckConstraint("version > 0", name="positive_version"),
        Index(
            "uq_open_clarification_per_request",
            "request_id",
            unique=True,
            sqlite_where=text("status = 'OPEN'"),
            postgresql_where=text("status = 'OPEN'"),
        ),
    )

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id", ondelete="RESTRICT"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    assigned_specialist_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    question: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    response_deadline: Mapped[date] = mapped_column(Date)
    status: Mapped[ClarificationStatus] = mapped_column(
        SqlEnum(
            ClarificationStatus,
            name="clarification_status",
            native_enum=False,
            create_constraint=True,
        ),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    closed_at: Mapped[datetime | None] = mapped_column(UTC_TS)

    request: Mapped[ServiceRequest] = relationship()
    requested_by: Mapped[User] = relationship(foreign_keys=[requested_by_user_id])
    assigned_specialist: Mapped[User] = relationship(
        foreign_keys=[assigned_specialist_id]
    )
    messages: Mapped[list[ClarificationMessage]] = relationship(
        back_populates="thread",
        order_by="ClarificationMessage.sequence",
    )


class ClarificationMessage(CreatedMixin, Base):
    __tablename__ = "clarification_messages"
    __table_args__ = (
        UniqueConstraint(
            "thread_id", "kind", name="uq_clarification_messages_thread_kind"
        ),
        UniqueConstraint(
            "thread_id",
            "sequence",
            name="uq_clarification_messages_thread_sequence",
        ),
        CheckConstraint("sequence > 0", name="positive_sequence"),
    )

    thread_id: Mapped[UUID] = mapped_column(
        ForeignKey("clarification_threads.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[ClarificationMessageKind] = mapped_column(
        SqlEnum(
            ClarificationMessageKind,
            name="clarification_message_kind",
            native_enum=False,
            create_constraint=True,
        )
    )
    body: Mapped[str] = mapped_column(Text)

    thread: Mapped[ClarificationThread] = relationship(back_populates="messages")
    actor: Mapped[User] = relationship()
