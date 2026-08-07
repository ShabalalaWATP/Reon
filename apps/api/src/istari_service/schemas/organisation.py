"""Public organisation hierarchy and metadata-only tracking schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from istari_service.models import RequestStatus
from istari_service.organisation_models import OrganisationKind, StaffingStatus
from istari_service.schemas.common import ApiModel


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


class TrackedRouteUnit(ApiModel):
    id: UUID
    name: str
    kind: OrganisationKind


class TrackedRequest(ApiModel):
    id: UUID
    reference: str
    status: RequestStatus
    current_owner: str | None
    required_by: date
    updated_at: datetime
    route: list[TrackedRouteUnit]
    awaiting_team_staffing: bool


class TrackedRequestList(ApiModel):
    items: list[TrackedRequest]
