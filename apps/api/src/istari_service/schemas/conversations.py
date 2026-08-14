"""Public contracts for request-scoped structured conversations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from istari_service.conversation_models import ConversationTargetType
from istari_service.models import UserRole
from istari_service.request_event_audience import RequestEventAudience
from istari_service.schemas.common import ApiModel, StrictApiModel
from istari_service.schemas.organisation import TrackedRequestEvent


class ConversationMessageCreate(StrictApiModel):
    body: Annotated[str, Field(min_length=3, max_length=2_000)]
    client_mutation_id: UUID
    subject: Annotated[str | None, Field(min_length=3, max_length=160)] = None
    target_type: ConversationTargetType | None = None
    target_unit_id: UUID | None = None
    conversation_id: UUID | None = None
    reply_to_message_id: UUID | None = None

    @field_validator("body", "subject")
    @classmethod
    def normalise_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value is not None else None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.conversation_id is None:
            if self.target_type is None:
                raise ValueError("A target is required for a new conversation.")
            if self.reply_to_message_id is not None:
                raise ValueError("A new conversation cannot reply to a message.")
            requires_unit = self.target_type is ConversationTargetType.ROUTE_UNIT
            if requires_unit != (self.target_unit_id is not None):
                raise ValueError("A route-unit target requires exactly one unit ID.")
        elif any(
            value is not None
            for value in (self.target_type, self.target_unit_id, self.subject)
        ):
            raise ValueError("A reply inherits its conversation target and subject.")
        return self


class ConversationTargetView(ApiModel):
    type: ConversationTargetType
    unit_id: UUID | None = None
    label: str


class ConversationMessageView(ApiModel):
    id: UUID
    sender_user_id: UUID
    sender_display_name: str
    sender_role: UserRole
    body: str
    reply_to_message_id: UUID | None
    created_at: datetime
    is_read: bool


class ConversationView(ApiModel):
    id: UUID
    subject: str
    target_type: ConversationTargetType
    target_unit_id: UUID | None
    target_label: str
    visibility: RequestEventAudience
    created_at: datetime
    messages: list[ConversationMessageView]
    unread_count: int
    messages_next_cursor: str | None = None


class ConversationWorkspace(ApiModel):
    allowed_targets: list[ConversationTargetView]
    conversations: list[ConversationView]
    conversations_next_cursor: str | None = None


class ConversationMutationResult(ApiModel):
    conversation: ConversationView
    event: TrackedRequestEvent


class ConversationReadResult(ApiModel):
    conversation_id: UUID
    unread_count: int
