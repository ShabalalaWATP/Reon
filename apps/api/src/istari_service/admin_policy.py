"""Persistence-independent administrator role and membership rules."""

from __future__ import annotations

from collections.abc import Sequence

from istari_service.models import UserRole
from istari_service.organisation_models import OrganisationKind

ROLE_UNIT_KIND: dict[UserRole, OrganisationKind | None] = {
    UserRole.PLATFORM_ADMIN: None,
    UserRole.REQUESTER: None,
    UserRole.INTAKE_TRIAGE: OrganisationKind.ROOT,
    UserRole.SERVICE_COORDINATION: OrganisationKind.COMMAND,
    UserRole.OPERATIONS_ALLOCATION: OrganisationKind.OPS_GROUP,
    UserRole.DELIVERY_TEAM_LEAD: OrganisationKind.TEAM,
    UserRole.DELIVERY_SPECIALIST: OrganisationKind.TEAM,
    UserRole.QUALITY_RELEASE: None,
}


def membership_error(
    role: UserRole,
    kinds: Sequence[OrganisationKind],
) -> str | None:
    expected = ROLE_UNIT_KIND[role]
    if expected is None:
        return "This role cannot hold organisation memberships." if kinds else None
    if not kinds:
        return "Select at least one compatible organisation unit."
    if any(kind is not expected for kind in kinds):
        return f"This role requires {expected.value} organisation units."
    if (
        role in {UserRole.DELIVERY_TEAM_LEAD, UserRole.DELIVERY_SPECIALIST}
        and len(kinds) != 1
    ):
        return "Team Managers and Analysts must belong to exactly one team."
    return None


def is_security_change(
    *,
    current_role: UserRole,
    next_role: UserRole,
    current_scope: str,
    next_scope: str,
    current_unit_ids: set[object],
    next_unit_ids: set[object],
) -> bool:
    return (
        current_role is not next_role
        or current_scope != next_scope
        or current_unit_ids != next_unit_ids
    )
