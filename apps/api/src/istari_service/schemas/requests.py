"""Service-request API schemas."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from istari_service.models import RequestStatus
from istari_service.schemas.common import ApiModel, StrictApiModel


class Sensitivity(StrEnum):
    STANDARD = "STANDARD"
    SENSITIVE = "SENSITIVE"
    RESTRICTED = "RESTRICTED"


class RequestCreate(StrictApiModel):
    submission_key: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=3, max_length=160)
    service_category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=20, max_length=5000)
    desired_outcome: str = Field(min_length=10, max_length=2000)
    background_context: str = Field(min_length=1, max_length=5000)
    required_by: date
    required_by_reason: str = Field(min_length=5, max_length=1000)
    preferred_deliverable_type: str = Field(min_length=2, max_length=80)
    success_criteria: str = Field(min_length=5, max_length=2000)
    requesting_business_area: str = Field(min_length=2, max_length=120)
    intended_recipients: list[str] = Field(min_length=1, max_length=20)
    sensitivity: Sensitivity
    handling_instructions: str = Field(min_length=1, max_length=2000)

    @field_validator("required_by")
    @classmethod
    def required_by_is_not_past(cls, value: date) -> date:
        if value < datetime.now(UTC).date():
            raise ValueError("requiredBy must not be in the past")
        return value

    @field_validator("intended_recipients")
    @classmethod
    def recipients_are_bounded(cls, value: list[str]) -> list[str]:
        cleaned = [recipient.strip() for recipient in value]
        if any(not recipient or len(recipient) > 120 for recipient in cleaned):
            raise ValueError("each intended recipient must contain 1 to 120 characters")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("intended recipients must be unique")
        return cleaned


class RequesterView(ApiModel):
    id: UUID
    display_name: str


class RequestEventView(ApiModel):
    id: UUID
    type: str
    message: str
    actor_display_name: str | None
    created_at: datetime


class DeliverableView(ApiModel):
    id: UUID
    title: str
    text: str
    released_at: datetime | None


class FeedbackCreate(StrictApiModel):
    submission_key: UUID = Field(default_factory=uuid4)
    rating: int = Field(ge=1, le=5)
    comments: str = Field(min_length=3, max_length=2000)


class FeedbackView(ApiModel):
    id: UUID
    rating: int
    comments: str
    created_at: datetime


class ClarificationMessageView(ApiModel):
    id: UUID
    kind: str
    body: str
    actor_display_name: str
    created_at: datetime


class ClarificationThreadView(ApiModel):
    id: UUID
    sequence: int
    question: str
    reason: str
    response_deadline: date
    status: str
    version: int
    assigned_specialist: RequesterView
    messages: list[ClarificationMessageView]
    created_at: datetime
    closed_at: datetime | None


class RequestSummary(ApiModel):
    id: UUID
    reference: str
    title: str
    status: RequestStatus
    current_owner: str
    required_by: date
    created_at: datetime
    updated_at: datetime
    needs_requester_input: bool
    product_available: bool = False
    feedback_submitted: bool = False


class RequestDetail(RequestSummary):
    service_category: str
    description: str
    desired_outcome: str
    background_context: str
    required_by_reason: str
    preferred_deliverable_type: str
    success_criteria: str
    requesting_business_area: str
    intended_recipients: list[str]
    sensitivity: Sensitivity
    handling_instructions: str
    requester: RequesterView
    assigned_delivery_team: str | None
    assigned_specialist: RequesterView | None
    events: list[RequestEventView]
    events_next_cursor: str | None = None
    deliverable: DeliverableView | None
    feedback: FeedbackView | None
    clarifications: list[ClarificationThreadView]
    workflow_error: str | None


class RequestList(ApiModel):
    items: list[RequestSummary]
    next_cursor: str | None = None
