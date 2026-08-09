"""Atomic projection of an activated configuration into stable unit identities."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_policy import LEVEL_BY_KIND
from istari_service.configuration_projection import (
    active_parents,
    active_units,
    candidate_groups,
)
from istari_service.configuration_types import (
    CandidateGroupPurpose,
    ConfigurationDraftSpec,
    StaffingCount,
    UnitRevisionSpec,
)
from istari_service.models import User, UserRole
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    StaffingStatus,
    UserOrganisationMembership,
)
from istari_service.repositories.configuration_staffing import load_staffing_counts
from istari_service.repositories.management import rebuild_organisation_closure


async def materialise_configuration_units(
    session: AsyncSession,
    specification: ConfigurationDraftSpec,
    *,
    at: datetime,
) -> None:
    """Upsert stable rows without deleting identities used by existing requests."""

    configured = active_units(specification, at)
    parents = active_parents(specification, at)
    groups = candidate_groups(specification)
    existing = {
        unit.id: unit
        for unit in await session.scalars(select(OrganisationUnit).with_for_update())
    }
    staffing = await load_staffing_counts(session, set(configured))
    next_sort_order = (
        max((unit.sort_order for unit in existing.values()), default=-1) + 1
    )
    ordered = sorted(
        configured.values(),
        key=lambda item: (LEVEL_BY_KIND[item.kind], item.code, str(item.unit_id)),
    )
    for revision in ordered:
        unit = existing.get(revision.unit_id)
        prior_name = unit.name if unit is not None else None
        if unit is None:
            unit = OrganisationUnit(id=revision.unit_id, sort_order=next_sort_order)
            next_sort_order += 1
            session.add(unit)
            existing[revision.unit_id] = unit
        _apply_revision(
            unit,
            revision,
            parent_id=parents.get(revision.unit_id),
            groups=groups.get(revision.unit_id, {}),
            staffing=staffing.get(revision.unit_id, StaffingCount()),
        )
        if revision.kind is OrganisationKind.TEAM and prior_name != revision.name:
            await _update_team_member_scopes(
                session,
                revision.unit_id,
                revision.name,
            )
    configured_ids = set(configured)
    for unit_id, unit in existing.items():
        if unit_id not in configured_ids and unit.is_configured:
            unit.is_configured = False
            unit.version = (unit.version or 0) + 1
    await session.flush()
    await rebuild_organisation_closure(session)


async def _update_team_member_scopes(
    session: AsyncSession,
    team_id: UUID,
    name: str,
) -> None:
    member_ids = select(UserOrganisationMembership.user_id).where(
        UserOrganisationMembership.unit_id == team_id
    )
    await session.execute(
        update(User)
        .where(
            User.id.in_(member_ids),
            User.role.in_([UserRole.DELIVERY_TEAM_LEAD, UserRole.DELIVERY_SPECIALIST]),
            User.scope != name,
        )
        .values(scope=name, version=User.version + 1)
        .execution_options(synchronize_session=False)
    )


def _apply_revision(
    unit: OrganisationUnit,
    revision: UnitRevisionSpec,
    *,
    parent_id: UUID | None,
    groups: dict[CandidateGroupPurpose, str],
    staffing: StaffingCount,
) -> bool:
    if revision.kind is OrganisationKind.TEAM:
        staffing_status = (
            StaffingStatus.STAFFED
            if staffing.managers >= revision.minimum_managers
            and staffing.analysts >= revision.minimum_analysts
            else StaffingStatus.UNSTAFFED
        )
        routing_group = None
        manager_group = groups.get(CandidateGroupPurpose.MANAGER)
        analyst_group = groups.get(CandidateGroupPurpose.ANALYST)
    else:
        staffing_status = StaffingStatus.ROUTING_POOL
        routing_group = groups.get(CandidateGroupPurpose.ROUTING)
        manager_group = None
        analyst_group = None
    changed = (
        unit.code != revision.code
        or unit.name != revision.name
        or unit.kind is not revision.kind
        or unit.parent_id != parent_id
        or unit.is_configured is not revision.routing_enabled
        or unit.staffing_status is not staffing_status
        or unit.routing_candidate_group != routing_group
        or unit.manager_candidate_group != manager_group
        or unit.analyst_candidate_group != analyst_group
    )
    if not changed:
        return False
    unit.code = revision.code
    unit.name = revision.name
    unit.kind = revision.kind
    unit.parent_id = parent_id
    unit.is_configured = revision.routing_enabled
    unit.staffing_status = staffing_status
    unit.routing_candidate_group = routing_group
    unit.manager_candidate_group = manager_group
    unit.analyst_candidate_group = analyst_group
    unit.version = (unit.version or 0) + 1
    return True
