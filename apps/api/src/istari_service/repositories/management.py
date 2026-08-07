"""Cycle-safe organisation closure and final-boundary management policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.management_models import (
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
    OrganisationClosure,
)
from istari_service.models import User
from istari_service.organisation_models import OrganisationUnit


@dataclass(frozen=True, slots=True)
class ManagementScope:
    grant_id: UUID
    root_unit_id: UUID
    target_unit_id: UUID
    include_descendants: bool
    action: ManagementAction
    grant_version: int


async def rebuild_organisation_closure(session: AsyncSession) -> int:
    """Rebuild all ancestor paths after rejecting missing parents and cycles."""

    units = list(await session.scalars(select(OrganisationUnit)))
    by_id = {unit.id: unit for unit in units}
    rows: list[OrganisationClosure] = []
    for unit in units:
        seen: set[UUID] = set()
        current = unit
        depth = 0
        while True:
            if current.id in seen:
                raise ValueError("The organisation hierarchy contains a cycle.")
            seen.add(current.id)
            rows.append(
                OrganisationClosure(
                    ancestor_id=current.id,
                    descendant_id=unit.id,
                    depth=depth,
                )
            )
            if current.parent_id is None:
                break
            parent = by_id.get(current.parent_id)
            if parent is None:
                raise ValueError("The organisation hierarchy has a missing parent.")
            current = parent
            depth += 1
    await session.execute(delete(OrganisationClosure))
    session.add_all(rows)
    await session.flush()
    return len(rows)


async def resolve_management_scope(
    session: AsyncSession,
    *,
    subject_user_id: UUID,
    grant_id: UUID,
    target_unit_id: UUID,
    action: ManagementAction,
    at: datetime | None = None,
    lock: bool = False,
) -> ManagementScope | None:
    """Resolve one client-named grant and target without trusting hierarchy input."""

    effective_at = at or datetime.now(UTC)
    query = (
        select(ManagementGrant, OrganisationClosure.depth)
        .join(User, User.id == ManagementGrant.subject_user_id)
        .join(
            ManagementGrantAction,
            ManagementGrantAction.grant_id == ManagementGrant.id,
        )
        .join(
            OrganisationClosure,
            and_(
                OrganisationClosure.ancestor_id == ManagementGrant.root_unit_id,
                OrganisationClosure.descendant_id == target_unit_id,
            ),
        )
        .join(
            OrganisationUnit,
            OrganisationUnit.id == OrganisationClosure.descendant_id,
        )
        .where(
            ManagementGrant.id == grant_id,
            ManagementGrant.subject_user_id == subject_user_id,
            ManagementGrantAction.action == action,
            ManagementGrant.effective_from <= effective_at,
            or_(
                ManagementGrant.effective_until.is_(None),
                ManagementGrant.effective_until > effective_at,
            ),
            ManagementGrant.revoked_at.is_(None),
            User.is_active.is_(True),
            OrganisationUnit.is_configured.is_(True),
        )
    )
    if lock:
        query = query.with_for_update()
    row = (await session.execute(query)).one_or_none()
    if row is None:
        return None
    grant, depth = row
    if depth > 0 and not grant.include_descendants:
        return None
    return ManagementScope(
        grant_id=grant.id,
        root_unit_id=grant.root_unit_id,
        target_unit_id=target_unit_id,
        include_descendants=grant.include_descendants,
        action=action,
        grant_version=grant.version,
    )


async def scoped_unit_ids(
    session: AsyncSession,
    scope: ManagementScope,
) -> tuple[UUID, ...]:
    """Return configured units under an already-authorised exact grant root."""

    query = (
        select(OrganisationClosure.descendant_id)
        .join(
            OrganisationUnit,
            OrganisationUnit.id == OrganisationClosure.descendant_id,
        )
        .where(
            OrganisationClosure.ancestor_id == scope.target_unit_id,
            OrganisationUnit.is_configured.is_(True),
        )
        .order_by(OrganisationClosure.depth, OrganisationUnit.sort_order)
    )
    if not scope.include_descendants:
        query = query.where(OrganisationClosure.depth == 0)
    return tuple(await session.scalars(query))
