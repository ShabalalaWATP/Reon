"""Organisation membership projection for synthetic local identities."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.models import User, UserRole
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    UserOrganisationMembership,
)
from istari_service.team_membership_seed import seed_team_membership_history
from istari_service.team_models import WorkspacePosition


class DemoMembershipIdentity(Protocol):
    @property
    def username(self) -> str: ...

    @property
    def role(self) -> UserRole: ...

    @property
    def unit_codes(self) -> tuple[str, ...]: ...

    @property
    def workspace_position(self) -> WorkspacePosition: ...


async def seed_demo_memberships(
    session: AsyncSession,
    users: dict[str, User],
    managed_usernames: set[str],
    identities: Sequence[DemoMembershipIdentity],
) -> None:
    if not managed_usernames:
        return
    units = (
        await session.scalars(
            select(OrganisationUnit).where(OrganisationUnit.is_configured.is_(True))
        )
    ).all()
    unit_by_code = {unit.code: unit for unit in units}
    ops_codes = tuple(
        unit.code for unit in units if unit.kind is OrganisationKind.OPS_GROUP
    )
    desired_codes = {
        identity.username: (
            identity.unit_codes
            or (ops_codes if identity.role is UserRole.OPERATIONS_ALLOCATION else ())
        )
        for identity in identities
        if identity.username in managed_usernames
    }
    managed_user_ids = {users[username].id for username in managed_usernames}
    memberships = (
        await session.scalars(
            select(UserOrganisationMembership).where(
                UserOrganisationMembership.user_id.in_(managed_user_ids)
            )
        )
    ).all()
    existing = {(item.user_id, item.unit_id): item for item in memberships}
    desired = {
        (users[username].id, unit_by_code[code].id)
        for username, codes in desired_codes.items()
        for code in codes
    }
    for key in desired - existing.keys():
        session.add(UserOrganisationMembership(user_id=key[0], unit_id=key[1]))
    for key in existing.keys() - desired:
        await session.delete(existing[key])
    await session.flush()
    positions = {
        (users[identity.username].id, unit_by_code[code].id): (
            WorkspacePosition.MANAGER
            if identity.role is UserRole.DELIVERY_TEAM_LEAD
            else identity.workspace_position
        )
        for identity in identities
        if identity.username in managed_usernames
        for code in desired_codes[identity.username]
    }
    await seed_team_membership_history(
        session,
        {
            (user_id, unit_id, positions[(user_id, unit_id)])
            for user_id, unit_id in desired
        },
        {unit.id for unit in units},
    )
