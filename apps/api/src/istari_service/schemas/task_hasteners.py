"""Exact-team Manager hastener contracts."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from istari_service.request_participant_models import RequestParticipantRole
from istari_service.schemas.common import ApiModel, StrictApiModel


class HastenerAudience(StrEnum):
    ONE_ASSIGNED = "ONE_ASSIGNED"
    ALL_ASSIGNED = "ALL_ASSIGNED"


class TaskHastenerCommand(StrictApiModel):
    audience: HastenerAudience
    recipient_user_id: UUID | None = None
    message: str = Field(min_length=10, max_length=500)

    @field_validator("message", mode="before")
    @classmethod
    def safe_message(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = unicodedata.normalize("NFKC", value).strip()
        if any(
            unicodedata.category(character) in {"Cc", "Cf"} for character in cleaned
        ):
            raise ValueError(
                "message cannot contain control or bidirectional characters"
            )
        return cleaned

    @model_validator(mode="after")
    def audience_matches_recipient(self) -> TaskHastenerCommand:
        if self.audience is HastenerAudience.ONE_ASSIGNED:
            if self.recipient_user_id is None:
                raise ValueError("recipientUserId is required for one Analyst")
        elif self.recipient_user_id is not None:
            raise ValueError("recipientUserId must be omitted for all Analysts")
        return self


class TaskHastenerRecipient(ApiModel):
    user_id: UUID
    display_name: str
    assignment_role: RequestParticipantRole


class TaskHastenerResult(ApiModel):
    event_id: UUID
    request_id: UUID
    message: str
    sender_display_name: str
    recipients: list[TaskHastenerRecipient]
    created_at: datetime
