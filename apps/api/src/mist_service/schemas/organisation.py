"""Public organisation hierarchy and route-scoped tracking schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from mist_service.models import RequestStatus
from mist_service.organisation_models import OrganisationKind, StaffingStatus
from mist_service.schemas.common import ApiModel
from mist_service.schemas.requests import CustomerUrgency, Sensitivity


class OrganisationUnitView(ApiModel):
    id: UUID
    code: str
    name: str
    kind: OrganisationKind
    parent_id: UUID | None
    staffing_status: StaffingStatus
    version: int


class OrganisationUnitList(ApiModel):
    items: list[OrganisationUnitView]


class RoutingPathUnit(ApiModel):
    id: UUID
    code: str
    name: str
    kind: OrganisationKind


class RoutingOptionsWorkspace(ApiModel):
    route: list[RoutingPathUnit]
    items: list[OrganisationUnitView]


class TrackedRouteUnit(ApiModel):
    id: UUID
    name: str
    kind: OrganisationKind


class TrackedRequest(ApiModel):
    id: UUID
    reference: str
    title: str
    status: RequestStatus
    current_owner: str | None
    required_by: date
    created_at: datetime
    updated_at: datetime
    route: list[TrackedRouteUnit]
    awaiting_team_staffing: bool
    age_days: int
    customer_acceptance_required: bool = False
    customer_accepted_at: datetime | None = None


class TrackedRequestEvent(ApiModel):
    id: UUID
    type: str
    message: str
    actor_display_name: str | None
    prior_status: RequestStatus | None
    next_status: RequestStatus | None
    created_at: datetime


class TrackedRequestDetail(TrackedRequest):
    requester_display_name: str
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
    events: list[TrackedRequestEvent]
    events_next_cursor: str | None = None


class TrackedRequestList(ApiModel):
    items: list[TrackedRequest]
    next_cursor: str | None = None
