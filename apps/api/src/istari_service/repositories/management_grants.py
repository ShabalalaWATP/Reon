"""Audited lifecycle operations for explicit management grants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.admin_audit import append_admin_event
from istari_service.errors import (
    AdministrationAccessDenied,
    InvalidAdministrationChange,
    ObjectNotFound,
    StaleVersion,
)
from istari_service.management_models import (
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
)
from istari_service.models import User, UserRole
from istari_service.organisation_models import OrganisationUnit


@dataclass(frozen=True, slots=True)
class GrantDefinition:
    subject_user_id: UUID
    root_unit_id: UUID
    include_descendants: bool
    actions: frozenset[ManagementAction]
    effective_from: datetime
    effective_until: datetime | None
    reason: str


async def create_management_grant(
    session: AsyncSession,
    *,
    actor_user_id: UUID,
    definition: GrantDefinition,
    supersedes_grant_id: UUID | None = None,
    version: int = 1,
) -> ManagementGrant:
    await _require_administrator(session, actor_user_id)
    await _validate_definition(session, definition)
    grant = ManagementGrant(
        subject_user_id=definition.subject_user_id,
        root_unit_id=definition.root_unit_id,
        include_descendants=definition.include_descendants,
        effective_from=definition.effective_from,
        effective_until=definition.effective_until,
        granted_by_user_id=actor_user_id,
        reason=definition.reason.strip(),
        supersedes_grant_id=supersedes_grant_id,
        version=version,
    )
    session.add(grant)
    await session.flush()
    session.add_all(
        ManagementGrantAction(grant_id=grant.id, action=action)
        for action in definition.actions
    )
    await append_admin_event(
        session,
        actor_id=actor_user_id,
        action="MANAGEMENT_GRANT_CREATED",
        target_type="MANAGEMENT_GRANT",
        target_id=grant.id,
        changed_fields=[
            "subjectUserId",
            "rootUnitId",
            "includeDescendants",
            "actions",
            "effectiveWindow",
        ],
        summary="Management authority created with a recorded reason.",
    )
    return grant


async def supersede_management_grant(
    session: AsyncSession,
    *,
    actor_user_id: UUID,
    grant_id: UUID,
    expected_version: int,
    definition: GrantDefinition,
    at: datetime | None = None,
) -> ManagementGrant:
    await _require_administrator(session, actor_user_id)
    grant = await _locked_grant(session, grant_id, expected_version)
    now = at or datetime.now(UTC)
    await _revoke(
        session,
        grant,
        actor_user_id=actor_user_id,
        reason=definition.reason,
        at=now,
        audit_action="MANAGEMENT_GRANT_SUPERSEDED",
    )
    return await create_management_grant(
        session,
        actor_user_id=actor_user_id,
        definition=definition,
        supersedes_grant_id=grant.id,
        version=grant.version,
    )


async def revoke_management_grant(
    session: AsyncSession,
    *,
    actor_user_id: UUID,
    grant_id: UUID,
    expected_version: int,
    reason: str,
    at: datetime | None = None,
) -> ManagementGrant:
    await _require_administrator(session, actor_user_id)
    grant = await _locked_grant(session, grant_id, expected_version)
    return await _revoke(
        session,
        grant,
        actor_user_id=actor_user_id,
        reason=reason,
        at=at or datetime.now(UTC),
        audit_action="MANAGEMENT_GRANT_REVOKED",
    )


async def _locked_grant(
    session: AsyncSession,
    grant_id: UUID,
    expected_version: int,
) -> ManagementGrant:
    grant = await session.scalar(
        select(ManagementGrant).where(ManagementGrant.id == grant_id).with_for_update()
    )
    if grant is None:
        raise ObjectNotFound()
    if grant.version != expected_version:
        raise StaleVersion()
    if grant.revoked_at is not None:
        raise InvalidAdministrationChange("This management grant is already inactive.")
    return grant


async def _revoke(
    session: AsyncSession,
    grant: ManagementGrant,
    *,
    actor_user_id: UUID,
    reason: str,
    at: datetime,
    audit_action: str,
) -> ManagementGrant:
    await _require_administrator(session, actor_user_id)
    _validate_reason(reason)
    grant.revoked_at = at
    grant.revoked_by_user_id = actor_user_id
    grant.revocation_reason = reason.strip()
    grant.version += 1
    await append_admin_event(
        session,
        actor_id=actor_user_id,
        action=audit_action,
        target_type="MANAGEMENT_GRANT",
        target_id=grant.id,
        changed_fields=["revokedAt", "revokedByUserId", "revocationReason"],
        summary="Management authority ended with a recorded reason.",
    )
    return grant


async def _require_administrator(session: AsyncSession, actor_user_id: UUID) -> None:
    actor = await session.scalar(
        select(User).where(
            User.id == actor_user_id,
            User.is_active.is_(True),
            User.role == UserRole.PLATFORM_ADMIN,
        )
    )
    if actor is None:
        raise AdministrationAccessDenied()


async def _validate_definition(
    session: AsyncSession,
    definition: GrantDefinition,
) -> None:
    _validate_reason(definition.reason)
    if not definition.actions:
        raise InvalidAdministrationChange("Select at least one management action.")
    if definition.effective_from.tzinfo is None or (
        definition.effective_until is not None
        and definition.effective_until.tzinfo is None
    ):
        raise InvalidAdministrationChange("Management grant times require a time zone.")
    if (
        definition.effective_until is not None
        and definition.effective_until <= definition.effective_from
    ):
        raise InvalidAdministrationChange("The management grant window is invalid.")
    subject = await session.scalar(
        select(User.id).where(
            User.id == definition.subject_user_id,
            User.is_active.is_(True),
        )
    )
    unit = await session.scalar(
        select(OrganisationUnit.id).where(
            OrganisationUnit.id == definition.root_unit_id,
            OrganisationUnit.is_configured.is_(True),
        )
    )
    if subject is None or unit is None:
        raise InvalidAdministrationChange(
            "Select an active account and configured organisation unit."
        )


def _validate_reason(reason: str) -> None:
    if not 10 <= len(reason.strip()) <= 500:
        raise InvalidAdministrationChange(
            "Give a management authority reason between 10 and 500 characters."
        )
