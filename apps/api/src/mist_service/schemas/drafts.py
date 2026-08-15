"""Private Customer request-draft API contracts."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from mist_service.schemas.common import ApiModel, StrictApiModel
from mist_service.schemas.requests import CustomerUrgency, RequestCreate, Sensitivity


class DraftFields(StrictApiModel):
    title: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    question_to_answer: str | None = Field(default=None, max_length=2000)
    desired_outcome: str | None = Field(default=None, max_length=2000)
    background_context: str | None = Field(default=None, max_length=5000)
    subject_area_or_location: str | None = Field(default=None, max_length=1000)
    coverage_start: date | None = None
    coverage_end: date | None = None
    customer_urgency: CustomerUrgency | None = None
    supported_activity_or_decision: str | None = Field(default=None, max_length=2000)
    required_by: date | None = None
    required_by_reason: str | None = Field(default=None, max_length=1000)
    preferred_deliverable_type: str | None = Field(default=None, max_length=80)
    success_criteria: str | None = Field(default=None, max_length=2000)
    constraints_or_caveats: str | None = Field(default=None, max_length=2000)
    supporting_information: str | None = Field(default=None, max_length=2000)
    sensitivity: Sensitivity | None = None
    handling_instructions: str | None = Field(default=None, max_length=2000)


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
    description: str | None
    question_to_answer: str | None
    desired_outcome: str | None
    background_context: str | None
    subject_area_or_location: str | None
    coverage_start: date | None
    coverage_end: date | None
    customer_urgency: CustomerUrgency | None
    supported_activity_or_decision: str | None
    required_by: date | None
    required_by_reason: str | None
    preferred_deliverable_type: str | None
    success_criteria: str | None
    constraints_or_caveats: str | None
    supporting_information: str | None
    sensitivity: Sensitivity | None
    handling_instructions: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class RequestDraftList(ApiModel):
    items: list[RequestDraftView]
    next_cursor: str | None = None
