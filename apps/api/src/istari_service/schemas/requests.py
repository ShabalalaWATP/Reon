"""Service-request API schemas."""

from __future__ import annotations

import unicodedata
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import ClassVar
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from istari_service.models import RequestStatus
from istari_service.schemas.common import ApiModel, StrictApiModel


class Sensitivity(StrEnum):
    STANDARD = "STANDARD"
    SENSITIVE = "SENSITIVE"
    RESTRICTED = "RESTRICTED"


class CustomerUrgency(StrEnum):
    ROUTINE = "ROUTINE"
    TIME_SENSITIVE = "TIME_SENSITIVE"
    IMMEDIATE = "IMMEDIATE"


class RequestCreate(StrictApiModel):
    submission_key: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=3, max_length=160)
    # Retained as server-owned persistence metadata for sealed historical
    # records. Customers no longer classify their own request.
    service_category: ClassVar[str] = "General service request"
    description: str = Field(min_length=20, max_length=5000)
    question_to_answer: str = Field(min_length=10, max_length=2000)
    desired_outcome: str = Field(min_length=10, max_length=2000)
    background_context: str = Field(min_length=1, max_length=5000)
    subject_area_or_location: str = Field(min_length=2, max_length=1000)
    coverage_start: date
    coverage_end: date
    customer_urgency: CustomerUrgency
    supported_activity_or_decision: str = Field(min_length=5, max_length=2000)
    required_by: date
    required_by_reason: str = Field(min_length=5, max_length=1000)
    preferred_deliverable_type: str = Field(min_length=2, max_length=80)
    success_criteria: str = Field(min_length=5, max_length=2000)
    constraints_or_caveats: str = Field(min_length=1, max_length=2000)
    supporting_information: str = Field(min_length=1, max_length=2000)
    sensitivity: Sensitivity
    handling_instructions: str = Field(min_length=1, max_length=2000)

    @field_validator("required_by")
    @classmethod
    def required_by_is_not_past(cls, value: date) -> date:
        if value < datetime.now(UTC).date():
            raise ValueError("requiredBy must not be in the past")
        return value

    @model_validator(mode="after")
    def coverage_period_is_ordered(self) -> RequestCreate:
        if self.coverage_end < self.coverage_start:
            raise ValueError("coverageEnd must not be before coverageStart")
        return self


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


class RequestCancel(StrictApiModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=1000)

    @field_validator("reason")
    @classmethod
    def safe_reason(cls, value: str) -> str:
        cleaned = unicodedata.normalize("NFKC", value).strip()
        unsafe = any(
            unicodedata.category(character) in {"Cc", "Cf"} for character in cleaned
        )
        if unsafe:
            raise ValueError(
                "reason cannot contain control or bidirectional characters"
            )
        return cleaned


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
    version: int
    needs_requester_input: bool
    product_available: bool = False
    feedback_submitted: bool = False


class RequestDetail(RequestSummary):
    service_category: str
    description: str
    question_to_answer: str
    desired_outcome: str
    background_context: str
    subject_area_or_location: str
    coverage_start: date
    coverage_end: date
    customer_urgency: CustomerUrgency
    supported_activity_or_decision: str
    required_by_reason: str
    preferred_deliverable_type: str
    success_criteria: str
    constraints_or_caveats: str
    supporting_information: str
    sensitivity: Sensitivity
    handling_instructions: str
    requester: RequesterView
    assigned_delivery_team: str | None
    assigned_specialist: RequesterView | None
    contributors: list[RequesterView] = Field(default_factory=list)
    events: list[RequestEventView]
    events_next_cursor: str | None = None
    deliverable: DeliverableView | None
    feedback: FeedbackView | None
    clarifications: list[ClarificationThreadView]
    workflow_error: str | None


class RequestList(ApiModel):
    items: list[RequestSummary]
    next_cursor: str | None = None
