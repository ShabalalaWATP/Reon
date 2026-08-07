"""Private Customer request-draft API contracts."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator

from istari_service.schemas.common import ApiModel, StrictApiModel
from istari_service.schemas.requests import RequestCreate, Sensitivity


class DraftFields(StrictApiModel):
    title: str | None = Field(default=None, max_length=160)
    service_category: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=5000)
    desired_outcome: str | None = Field(default=None, max_length=2000)
    background_context: str | None = Field(default=None, max_length=5000)
    required_by: date | None = None
    required_by_reason: str | None = Field(default=None, max_length=1000)
    preferred_deliverable_type: str | None = Field(default=None, max_length=80)
    success_criteria: str | None = Field(default=None, max_length=2000)
    requesting_business_area: str | None = Field(default=None, max_length=120)
    intended_recipients: list[str] | None = Field(default=None, max_length=20)
    sensitivity: Sensitivity | None = None
    handling_instructions: str | None = Field(default=None, max_length=2000)

    @field_validator("intended_recipients")
    @classmethod
    def draft_recipients_are_bounded(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [recipient.strip() for recipient in value if recipient.strip()]
        if any(len(recipient) > 120 for recipient in cleaned):
            raise ValueError(
                "each intended recipient must contain at most 120 characters"
            )
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("intended recipients must be unique")
        return cleaned


class RequestDraftCreate(DraftFields):
    pass


class RequestDraftUpdate(DraftFields):
    expected_version: int = Field(ge=1)


class RequestDraftSubmit(RequestCreate):
    expected_version: int = Field(ge=1)


class RequestDraftView(ApiModel):
    id: UUID
    requester_id: UUID
    title: str | None
    service_category: str | None
    description: str | None
    desired_outcome: str | None
    background_context: str | None
    required_by: date | None
    required_by_reason: str | None
    preferred_deliverable_type: str | None
    success_criteria: str | None
    requesting_business_area: str | None
    intended_recipients: list[str] | None
    sensitivity: Sensitivity | None
    handling_instructions: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class RequestDraftList(ApiModel):
    items: list[RequestDraftView]
