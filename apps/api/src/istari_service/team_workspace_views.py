"""Pure row-to-contract projections for team workspaces."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from istari_service.models import User
from istari_service.organisation_models import OrganisationUnit
from istari_service.schemas.team_workspaces import (
    EligibleRosterAnalyst,
    MembershipState,
    TeamActivity,
    TeamMember,
    TeamWorkspaceAccess,
)
from istari_service.team_models import TeamMembership


def access_pair(access: TeamWorkspaceAccess) -> tuple[UUID, TeamWorkspaceAccess]:
    return access.team_id, access


def member_user_id(row: Any) -> UUID:
    return cast(UUID, row[1].id)


def user_id(user: User) -> UUID:
    return user.id


def current_membership_pair(
    row: Any,
) -> tuple[UUID, tuple[TeamMembership, OrganisationUnit]]:
    return row[0].user_id, (row[0], row[1])


def work_count_pair(row: Any) -> tuple[UUID, int]:
    return row[0], row[1]


def member_view(
    row: Any,
    *,
    now: datetime,
    active_counts: dict[UUID, int],
    reveal_reasons: bool,
) -> TeamMember:
    membership, user = row
    return TeamMember(
        membership_id=membership.id,
        account_id=user.id,
        display_name=user.display_name,
        role=user.role,
        workspace_position=membership.workspace_position,
        state=_membership_state(membership, now),
        effective_from=_as_utc(membership.effective_from),
        effective_until=(
            _as_utc(membership.effective_until)
            if membership.effective_until is not None
            else None
        ),
        version=membership.version,
        active_work_count=active_counts.get(user.id, 0),
        skills=user.skills,
        start_reason=membership.start_reason if reveal_reasons else None,
        end_reason=membership.end_reason if reveal_reasons else None,
    )


def eligible_view(
    analyst: User,
    *,
    current_by_user: dict[UUID, tuple[TeamMembership, OrganisationUnit]],
    active_counts: dict[UUID, int],
) -> EligibleRosterAnalyst:
    row = current_by_user.get(analyst.id)
    membership, team = row if row else (None, None)
    return EligibleRosterAnalyst(
        account_id=analyst.id,
        display_name=analyst.display_name,
        current_team_id=team.id if team else None,
        current_team_name=team.name if team else None,
        current_membership_id=membership.id if membership else None,
        current_membership_version=membership.version if membership else None,
        active_work_count=active_counts.get(analyst.id, 0),
    )


def activity_view(row: Any) -> TeamActivity:
    event, actor_name, subject_name = row
    return TeamActivity(
        id=event.id,
        type=event.type,
        summary=event.summary,
        actor_display_name=actor_name,
        subject_display_name=subject_name,
        created_at=event.created_at,
    )


def _membership_state(membership: TeamMembership, now: datetime) -> MembershipState:
    effective_from = _as_utc(membership.effective_from)
    effective_until = (
        _as_utc(membership.effective_until)
        if membership.effective_until is not None
        else None
    )
    if effective_from > now:
        return MembershipState.SCHEDULED
    if effective_until is not None and effective_until <= now:
        return MembershipState.ENDED
    return MembershipState.CURRENT


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
