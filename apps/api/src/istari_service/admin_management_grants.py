"""Synchronise the standard exact-team authority for admin-managed Managers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.management_models import ManagementAction, ManagementGrant
from istari_service.models import UserRole
from istari_service.repositories.management_grants import (
    GrantDefinition,
    create_management_grant,
    revoke_management_grant,
)

STANDARD_MANAGER_GRANT_REASON = (
    "Standard exact-team authority for an Administrator-managed Team Manager."
)
STANDARD_MANAGER_REVOCATION_REASON = (
    "Administrator changed the Manager's role, team or account status."
)


async def synchronise_admin_manager_grant(
    session: AsyncSession,
    *,
    actor_user_id: UUID,
    subject_user_id: UUID,
    role: UserRole,
    team_id: UUID | None,
    is_active: bool,
) -> None:
    active = list(
        await session.scalars(
            select(ManagementGrant)
            .where(
                ManagementGrant.subject_user_id == subject_user_id,
                ManagementGrant.reason == STANDARD_MANAGER_GRANT_REASON,
                ManagementGrant.revoked_at.is_(None),
            )
            .with_for_update()
        )
    )
    expected_team = (
        team_id if role is UserRole.DELIVERY_TEAM_LEAD and is_active else None
    )
    matching = next(
        (grant for grant in active if grant.root_unit_id == expected_team),
        None,
    )
    for grant in active:
        if grant is matching:
            continue
        await revoke_management_grant(
            session,
            actor_user_id=actor_user_id,
            grant_id=grant.id,
            expected_version=grant.version,
            reason=STANDARD_MANAGER_REVOCATION_REASON,
        )
    if expected_team is None or matching is not None:
        return
    await create_management_grant(
        session,
        actor_user_id=actor_user_id,
        definition=GrantDefinition(
            subject_user_id=subject_user_id,
            root_unit_id=expected_team,
            include_descendants=False,
            actions=frozenset(ManagementAction),
            effective_from=datetime.now(UTC),
            effective_until=None,
            reason=STANDARD_MANAGER_GRANT_REASON,
        ),
    )
