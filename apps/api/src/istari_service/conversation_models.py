"""Immutable request conversations and recipient read state."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as rel

from istari_service.models import UTC_TS, Base, CreatedMixin, User, UserRole, _enum
from istari_service.request_event_audience import RequestEventAudience

if TYPE_CHECKING:
    from istari_service.request_event_models import RequestEvent


class ConversationTargetType(StrEnum):
    CUSTOMER = "CUSTOMER"
    CURRENT_OWNER = "CURRENT_OWNER"
    TEAM_MANAGERS = "TEAM_MANAGERS"
    ASSIGNED_ANALYSTS = "ASSIGNED_ANALYSTS"
    ROUTE_UNIT = "ROUTE_UNIT"
    QC_TEAM = "QC_TEAM"


class RequestConversation(CreatedMixin, Base):
    __tablename__ = "request_conversations"
    __table_args__ = (
        Index(
            "ix_request_conversations_request_created",
            "request_id",
            "created_at",
            "id",
        ),
    )

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id", ondelete="CASCADE"), index=True
    )
    opened_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    target_type: Mapped[ConversationTargetType] = mapped_column(
        _enum(ConversationTargetType, "conversation_target_type"), index=True
    )
    target_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    target_label: Mapped[str] = mapped_column(String(160))
    subject: Mapped[str] = mapped_column(String(160))
    visibility: Mapped[RequestEventAudience] = mapped_column(
        _enum(RequestEventAudience, "conversation_visibility"), index=True
    )
    opened_by: Mapped[User] = rel(foreign_keys=[opened_by_user_id])
    messages: Mapped[list[RequestConversationMessage]] = rel(
        back_populates="conversation",
        order_by="RequestConversationMessage.created_at, RequestConversationMessage.id",
        lazy="raise",
    )


class RequestConversationMessage(CreatedMixin, Base):
    __tablename__ = "request_conversation_messages"
    __table_args__ = (
        UniqueConstraint(
            "sender_user_id",
            "client_mutation_id",
            name="uq_conversation_message_sender_mutation",
        ),
        Index(
            "ix_conversation_messages_conversation_created",
            "conversation_id",
            "created_at",
            "id",
        ),
    )

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("request_conversations.id", ondelete="CASCADE"), index=True
    )
    sender_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    sender_role: Mapped[UserRole] = mapped_column(
        _enum(UserRole, "conversation_sender_role")
    )
    body: Mapped[str] = mapped_column(Text)
    body_sha256: Mapped[str] = mapped_column(String(64))
    reply_to_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("request_conversation_messages.id", ondelete="RESTRICT")
    )
    client_mutation_id: Mapped[UUID] = mapped_column(index=True)
    request_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("request_events.id", ondelete="RESTRICT"), unique=True
    )
    conversation: Mapped[RequestConversation] = rel(back_populates="messages")
    sender: Mapped[User] = rel(foreign_keys=[sender_user_id], lazy="raise")
    request_event: Mapped[RequestEvent] = rel(
        foreign_keys=[request_event_id], lazy="raise"
    )
    deliveries: Mapped[list[RequestConversationDelivery]] = rel(
        back_populates="message", lazy="raise"
    )


class RequestConversationDelivery(CreatedMixin, Base):
    __tablename__ = "request_conversation_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "recipient_user_id",
            name="uq_conversation_delivery_recipient",
        ),
        Index(
            "ix_conversation_deliveries_recipient_read",
            "recipient_user_id",
            "read_at",
        ),
    )

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("request_conversation_messages.id", ondelete="CASCADE"),
        index=True,
    )
    recipient_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    message: Mapped[RequestConversationMessage] = rel(back_populates="deliveries")
