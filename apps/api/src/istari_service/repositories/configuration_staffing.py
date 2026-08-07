"""Read-only staffing projection used by configuration validation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_types import StaffingCount
from istari_service.models import User, UserRole
from istari_service.organisation_models import UserOrganisationMembership


async def load_staffing_counts(
    session: AsyncSession, unit_ids: set[UUID]
) -> dict[UUID, StaffingCount]:
    if not unit_ids:
        return {}
    rows = (
        await session.execute(
            select(
                UserOrganisationMembership.unit_id,
                User.role,
                func.count(User.id),
            )
            .join(User, User.id == UserOrganisationMembership.user_id)
            .where(
                UserOrganisationMembership.unit_id.in_(unit_ids),
                User.is_active.is_(True),
                User.role.in_(
                    [UserRole.DELIVERY_TEAM_LEAD, UserRole.DELIVERY_SPECIALIST]
                ),
            )
            .group_by(UserOrganisationMembership.unit_id, User.role)
        )
    ).all()
    counts: dict[UUID, StaffingCount] = {}
    for unit_id, role, raw_count in rows:
        current = counts.get(unit_id, StaffingCount())
        count = int(raw_count)
        counts[unit_id] = StaffingCount(
            managers=count if role is UserRole.DELIVERY_TEAM_LEAD else current.managers,
            analysts=count
            if role is UserRole.DELIVERY_SPECIALIST
            else current.analysts,
        )
    return counts
