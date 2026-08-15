"""Authorised team workspace and roster contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from mist_service.management_models import ManagementAction
from mist_service.models import UserRole
from mist_service.organisation_models import OrganisationKind
from mist_service.schemas.common import ApiModel, StrictApiModel
from mist_service.team_models import WorkspacePosition


class MembershipState(StrEnum):
    CURRENT = "CURRENT"
    SCHEDULED = "SCHEDULED"
    ENDED = "ENDED"


class TeamWorkspaceAccess(ApiModel):
    team_id: UUID
    team_code: str
    team_name: str
    unit_kind: OrganisationKind
    workspace_position: WorkspacePosition | None
    grant_id: UUID | None
    permissions: list[ManagementAction]
    views: list[str]


class TeamWorkspaceList(ApiModel):
    items: list[TeamWorkspaceAccess]


class TeamWorkspaceOverview(ApiModel):
    access: TeamWorkspaceAccess
    manager_count: int = Field(ge=0)
    member_count: int = Field(ge=0)
    analyst_count: int = Field(ge=0)
    active_work_count: int = Field(ge=0)
    due_soon_count: int = Field(ge=0)
    overdue_count: int = Field(ge=0)


class TeamMember(ApiModel):
    membership_id: UUID
    account_id: UUID
    display_name: str
    role: UserRole
    workspace_position: WorkspacePosition
    state: MembershipState
    effective_from: datetime
    effective_until: datetime | None
    version: int
    active_work_count: int = Field(ge=0)
    skills: list[str]
    start_reason: str | None
    end_reason: str | None


class TeamPeople(ApiModel):
    items: list[TeamMember]


class TeamMemberProfile(ApiModel):
    account_id: UUID
    name: str
    email: str
    role: UserRole
    team_id: UUID
    team_name: str
    workspace_position: WorkspacePosition
    membership_state: MembershipState
    rank_or_grade: str | None
    skills: list[str]
    account_active: bool


class EligibleRosterAnalyst(ApiModel):
    account_id: UUID
    display_name: str
    current_team_id: UUID | None
    current_team_name: str | None
    current_membership_id: UUID | None
    current_membership_version: int | None
    active_work_count: int = Field(ge=0)


class EligibleRosterAnalystList(ApiModel):
    items: list[EligibleRosterAnalyst]


class TeamActivity(ApiModel):
    id: UUID
    type: str
    summary: str
    actor_display_name: str | None
    subject_display_name: str
    created_at: datetime


class TeamActivityList(ApiModel):
    items: list[TeamActivity]


class RosterCommand(StrictApiModel):
    grant_id: UUID
    analyst_id: UUID
    reason: str = Field(min_length=10, max_length=500)


class TransferCommand(RosterCommand):
    current_membership_id: UUID
    expected_version: int = Field(ge=1)
    effective_from: datetime

    @field_validator("effective_from")
    @classmethod
    def require_time_zone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("effectiveFrom requires a time zone")
        return value


class EndMembershipCommand(StrictApiModel):
    grant_id: UUID
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=500)


WorkspaceView = Literal[
    "OVERVIEW",
    "BOARD",
    "QUEUE",
    "CALENDAR",
    "PEOPLE",
    "PLANNING",
    "STATISTICS",
    "HANDOVER",
    "ACTIVITY",
]
