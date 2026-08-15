"""Synchronise the standard exact-team authority for admin-managed Managers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.management_models import ManagementAction, ManagementGrant
from mist_service.models import UserRole
from mist_service.organisation_models import OrganisationKind, OrganisationUnit
from mist_service.repositories.management_grants import (
    GrantDefinition,
    create_management_grant,
    revoke_management_grant,
)
from mist_service.team_models import WorkspacePosition

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
    unit_ids: set[UUID],
    workspace_position: WorkspacePosition | None,
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
    expected = await _expected_grants(
        session,
        role=role,
        unit_ids=unit_ids,
        position=workspace_position,
        is_active=is_active,
    )
    matching = {
        (grant.root_unit_id, grant.include_descendants): grant
        for grant in active
        if (grant.root_unit_id, grant.include_descendants) in expected
    }
    for grant in active:
        if grant in matching.values():
            continue
        await revoke_management_grant(
            session,
            actor_user_id=actor_user_id,
            grant_id=grant.id,
            expected_version=grant.version,
            reason=STANDARD_MANAGER_REVOCATION_REASON,
        )
    for key, actions in expected.items():
        if key in matching:
            continue
        unit_id, include_descendants = key
        await create_management_grant(
            session,
            actor_user_id=actor_user_id,
            definition=GrantDefinition(
                subject_user_id=subject_user_id,
                root_unit_id=unit_id,
                include_descendants=include_descendants,
                actions=frozenset(actions),
                effective_from=datetime.now(UTC),
                effective_until=None,
                reason=STANDARD_MANAGER_GRANT_REASON,
            ),
        )


async def _expected_grants(
    session: AsyncSession,
    *,
    role: UserRole,
    unit_ids: set[UUID],
    position: WorkspacePosition | None,
    is_active: bool,
) -> dict[tuple[UUID, bool], set[ManagementAction]]:
    if (
        role is UserRole.QUALITY_RELEASE
        or not is_active
        or position is not WorkspacePosition.MANAGER
        or not unit_ids
    ):
        return {}
    rows = (
        await session.execute(
            select(OrganisationUnit.id, OrganisationUnit.kind).where(
                OrganisationUnit.id.in_(unit_ids)
            )
        )
    ).all()
    expected: dict[tuple[UUID, bool], set[ManagementAction]] = {}
    for unit_id, kind in rows:
        if kind is OrganisationKind.TEAM and role is UserRole.DELIVERY_TEAM_LEAD:
            expected[(unit_id, False)] = set(ManagementAction)
            continue
        expected[(unit_id, False)] = {
            ManagementAction.ROSTER,
            ManagementAction.CALENDAR,
        }
        expected[(unit_id, True)] = {ManagementAction.STATISTICS}
    return expected
