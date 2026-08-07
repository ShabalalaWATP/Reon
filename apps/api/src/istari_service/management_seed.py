"""Deterministic local management grants for synthetic users."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.management_models import (
    MANAGEMENT_SEED_REASON,
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
)
from istari_service.models import User, UserRole
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    UserOrganisationMembership,
)

MANAGEMENT_NAMESPACE = UUID("b1979c10-bd60-4a46-852b-2f59cb777961")
SEED_EFFECTIVE_FROM = datetime(2026, 1, 1, tzinfo=UTC)
ALL_TEAM_ACTIONS = tuple(ManagementAction)

NAMED_STATISTICS_GRANTS = {
    "admin4": ("JIOC",),
    "admin5": ("DIGOC", "SYGOC", "MYGOC"),
    "admin6": (
        "NCGI_A_OPS",
        "AURORA_OPS",
        "VERTEX_OPS",
        "NIMBUS_OPS",
        "PARALLAX_OPS",
    ),
    "admin10": (
        "HORIZON_OPS",
        "MERIDIAN_OPS",
        "SOLSTICE_OPS",
        "FRONTIER_OPS",
    ),
}


def management_grant_id(username: str, unit_code: str) -> UUID:
    return uuid5(MANAGEMENT_NAMESPACE, f"{username}:{unit_code}")


async def seed_management_grants(session: AsyncSession) -> int:
    """Add missing fixtures without overwriting later administrator changes."""

    users = list(await session.scalars(select(User)))
    units = list(
        await session.scalars(
            select(OrganisationUnit).where(OrganisationUnit.is_configured.is_(True))
        )
    )
    by_username = {user.username: user for user in users}
    by_code = {unit.code: unit for unit in units}
    administrator = by_username.get("admin1")
    if administrator is None:
        return 0
    definitions: list[tuple[User, OrganisationUnit, tuple[ManagementAction, ...]]] = []
    for username, unit_codes in NAMED_STATISTICS_GRANTS.items():
        subject = by_username.get(username)
        if subject is None or not subject.is_active:
            continue
        for unit_code in unit_codes:
            definitions.append(
                (subject, by_code[unit_code], (ManagementAction.STATISTICS,))
            )
    definitions.extend(await _team_manager_definitions(session, by_code))
    existing_ids = set(
        await session.scalars(
            select(ManagementGrant.id).where(
                ManagementGrant.id.in_(
                    management_grant_id(subject.username, unit.code)
                    for subject, unit, _actions in definitions
                )
            )
        )
    )
    created = 0
    for subject, unit, actions in definitions:
        grant_id = management_grant_id(subject.username, unit.code)
        if grant_id in existing_ids:
            continue
        grant = ManagementGrant(
            id=grant_id,
            subject_user_id=subject.id,
            root_unit_id=unit.id,
            include_descendants=unit.kind is not OrganisationKind.TEAM,
            effective_from=SEED_EFFECTIVE_FROM,
            effective_until=None,
            granted_by_user_id=administrator.id,
            reason=MANAGEMENT_SEED_REASON,
        )
        session.add(grant)
        session.add_all(
            ManagementGrantAction(grant_id=grant_id, action=action)
            for action in actions
        )
        created += 1
    await session.flush()
    return created


async def _team_manager_definitions(
    session: AsyncSession,
    by_code: dict[str, OrganisationUnit],
) -> list[tuple[User, OrganisationUnit, tuple[ManagementAction, ...]]]:
    rows = (
        await session.execute(
            select(User, OrganisationUnit.code)
            .join(
                UserOrganisationMembership,
                UserOrganisationMembership.user_id == User.id,
            )
            .join(
                OrganisationUnit,
                OrganisationUnit.id == UserOrganisationMembership.unit_id,
            )
            .where(
                User.role == UserRole.DELIVERY_TEAM_LEAD,
                User.is_active.is_(True),
                OrganisationUnit.kind == OrganisationKind.TEAM,
                OrganisationUnit.is_configured.is_(True),
            )
        )
    ).all()
    return [(user, by_code[code], ALL_TEAM_ACTIONS) for user, code in rows]
