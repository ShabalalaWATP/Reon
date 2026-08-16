"""Role-scoped work-item schemas and allowed completion commands."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from mist_service.models import RequestStatus
from mist_service.schemas.common import ApiModel, StrictApiModel


class RequestInformation(StrictApiModel):
    action: Literal["request_information"]
    reason: str = Field(min_length=3, max_length=2000)


class ProgressRequest(StrictApiModel):
    action: Literal["progress"]
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"]
    destination_unit_id: UUID
    # Optional: a routing decision with nothing to add is legitimate, and the
    # activity record then carries the default label for the receiving team.
    note: str | None = Field(default=None, min_length=3, max_length=2000)


class CloseRequest(StrictApiModel):
    action: Literal["close"]
    reason: str = Field(min_length=3, max_length=2000)


class ProvideInformation(StrictApiModel):
    action: Literal["provide_information"]
    information: str = Field(min_length=3, max_length=5000)


class WithdrawRequest(StrictApiModel):
    action: Literal["withdraw"]
    reason: str = Field(min_length=3, max_length=2000)


class SendToAllocation(StrictApiModel):
    action: Literal["send_to_allocation"]
    destination_unit_id: UUID
    note: str = Field(min_length=3, max_length=2000)


class ReturnToTriage(StrictApiModel):
    action: Literal["return_to_triage"]
    reason: str = Field(min_length=3, max_length=2000)


class HoldRequest(StrictApiModel):
    action: Literal["hold"]
    reason: str = Field(min_length=3, max_length=2000)


class ResumeRequest(StrictApiModel):
    action: Literal["resume"]
    note: str = Field(min_length=3, max_length=2000)


class AllocateRequest(StrictApiModel):
    action: Literal["allocate"]
    destination_unit_id: UUID
    required_capabilities: list[str] = Field(min_length=1, max_length=20)

    @field_validator("required_capabilities")
    @classmethod
    def capabilities_are_bounded(cls, value: list[str]) -> list[str]:
        return _bounded_unique_strings(value, "required capability")


class ReturnToCoordination(StrictApiModel):
    action: Literal["return_to_coordination"]
    reason: str = Field(min_length=3, max_length=2000)


class AssignSpecialist(StrictApiModel):
    action: Literal["assign"]
    specialist_id: UUID
    contributor_ids: list[UUID] = Field(default_factory=list, max_length=10)
    reason: str = Field(min_length=10, max_length=500)

    @field_validator("contributor_ids")
    @classmethod
    def contributors_are_unique(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Contributors must be unique.")
        return value

    @field_validator("reason", mode="before")
    @classmethod
    def reason_is_not_blank(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReturnForReallocation(StrictApiModel):
    action: Literal["return_for_reallocation"]
    reason: str = Field(min_length=3, max_length=2000)


class SubmitDeliverable(StrictApiModel):
    action: Literal["submit"]
    managed_product: bool = False
    deliverable_title: str | None = Field(default=None, min_length=3, max_length=160)
    deliverable_text: str | None = Field(default=None, min_length=20, max_length=20_000)

    @model_validator(mode="after")
    def exactly_one_product_mode(self) -> SubmitDeliverable:
        legacy = (
            self.deliverable_title is not None and self.deliverable_text is not None
        )
        if self.managed_product == legacy:
            raise ValueError("submit either a managed package or a legacy product")
        return self


class RequestClarification(StrictApiModel):
    action: Literal["request_clarification"]
    question: str = Field(min_length=3, max_length=2000)
    reason: str = Field(min_length=3, max_length=2000)
    response_deadline: date


class ProvideClarification(StrictApiModel):
    action: Literal["provide_clarification"]
    thread_id: UUID
    expected_version: int = Field(ge=1)
    information: str = Field(min_length=3, max_length=5000)


class ApproveWork(StrictApiModel):
    action: Literal["approve"]


class ChangesRequired(StrictApiModel):
    action: Literal["changes_required"]
    reason: str = Field(min_length=3, max_length=2000)


class ReleaseDeliverable(StrictApiModel):
    action: Literal["release"]
    managed_product: bool = False
    recipients: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def exactly_one_release_mode(self) -> ReleaseDeliverable:
        if self.managed_product == bool(self.recipients):
            raise ValueError("release either a managed package or a legacy product")
        return self

    @field_validator("recipients")
    @classmethod
    def recipients_are_bounded(cls, value: list[str]) -> list[str]:
        return _bounded_unique_strings(value, "recipient")


def _bounded_unique_strings(value: list[str], label: str) -> list[str]:
    cleaned = [item.strip() for item in value]
    if any(not item or len(item) > 120 for item in cleaned):
        raise ValueError(f"each {label} must contain 1 to 120 characters")
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"{label}s must be unique")
    return cleaned


CompletionPayload = Annotated[
    RequestInformation
    | ProgressRequest
    | CloseRequest
    | ProvideInformation
    | WithdrawRequest
    | SendToAllocation
    | ReturnToTriage
    | HoldRequest
    | ResumeRequest
    | AllocateRequest
    | ReturnToCoordination
    | AssignSpecialist
    | ReturnForReallocation
    | SubmitDeliverable
    | RequestClarification
    | ProvideClarification
    | ApproveWork
    | ChangesRequired
    | ReleaseDeliverable,
    Field(discriminator="action"),
]


class WorkItem(ApiModel):
    id: UUID
    request_id: UUID
    request_reference: str
    request_version: int
    title: str
    stage: RequestStatus
    status: str
    assignee_id: UUID | None
    assignee_display_name: str | None
    delivery_team: str | None
    available_actions: list[str]
    assigned_to_current_user: bool = False
    assignment_role: Literal["LEAD_ANALYST", "ANALYST"] | None = None
    created_at: datetime
    updated_at: datetime


class WorkItemList(ApiModel):
    items: list[WorkItem]
    next_cursor: str | None = None


class EligibleSpecialist(ApiModel):
    id: UUID
    display_name: str


class EligibleSpecialistList(ApiModel):
    items: list[EligibleSpecialist]
