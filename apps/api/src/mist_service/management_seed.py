"""Deterministic local management grants for synthetic users."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.management_models import (
    MANAGEMENT_SEED_REASON,
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
)
from mist_service.models import User
from mist_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
)
from mist_service.team_models import TeamMembership, WorkspacePosition

MANAGEMENT_NAMESPACE = UUID("b1979c10-bd60-4a46-852b-2f59cb777961")
SEED_EFFECTIVE_FROM = datetime(2026, 1, 1, tzinfo=UTC)
ALL_TEAM_ACTIONS = tuple(ManagementAction)

NAMED_STATISTICS_GRANTS = {
    "admin4": ("CRIOC",),
    "admin5": ("JOCK", "SYGOC", "MYGOC"),
    "admin6": (
        "ACSA_B_OPS",
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
    "admin15": ("CRIOC",),
}


def management_grant_id(
    username: str, unit_code: str, purpose: str = "statistics"
) -> UUID:
    suffix = "" if purpose == "statistics" else f":{purpose}"
    return uuid5(MANAGEMENT_NAMESPACE, f"{username}:{unit_code}{suffix}")


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
    definitions: list[
        tuple[
            User,
            OrganisationUnit,
            tuple[ManagementAction, ...],
            bool,
            str,
        ]
    ] = []
    for username, unit_codes in NAMED_STATISTICS_GRANTS.items():
        subject = by_username.get(username)
        if subject is None or not subject.is_active:
            continue
        for unit_code in unit_codes:
            definitions.append(
                (
                    subject,
                    by_code[unit_code],
                    (ManagementAction.STATISTICS,),
                    True,
                    "statistics",
                )
            )
    definitions.extend(await _workspace_manager_definitions(session, by_code))
    definitions_by_id = {
        management_grant_id(subject.username, unit.code, purpose): definition
        for definition in definitions
        for subject, unit, _actions, _descendants, purpose in (definition,)
    }
    existing_ids = set(
        await session.scalars(
            select(ManagementGrant.id).where(ManagementGrant.id.in_(definitions_by_id))
        )
    )
    created = 0
    for grant_id, definition in definitions_by_id.items():
        subject, unit, actions, include_descendants, _purpose = definition
        if grant_id in existing_ids:
            continue
        grant = ManagementGrant(
            id=grant_id,
            subject_user_id=subject.id,
            root_unit_id=unit.id,
            include_descendants=include_descendants,
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


async def _workspace_manager_definitions(
    session: AsyncSession,
    by_code: dict[str, OrganisationUnit],
) -> list[tuple[User, OrganisationUnit, tuple[ManagementAction, ...], bool, str]]:
    rows = (
        await session.execute(
            select(User, OrganisationUnit.code)
            .join(
                TeamMembership,
                TeamMembership.user_id == User.id,
            )
            .join(
                OrganisationUnit,
                OrganisationUnit.id == TeamMembership.team_id,
            )
            .where(
                TeamMembership.workspace_position == WorkspacePosition.MANAGER,
                TeamMembership.effective_from <= datetime.now(UTC),
                TeamMembership.effective_until.is_(None),
                User.is_active.is_(True),
                OrganisationUnit.is_configured.is_(True),
            )
        )
    ).all()
    definitions: list[
        tuple[User, OrganisationUnit, tuple[ManagementAction, ...], bool, str]
    ] = []
    for user, code in rows:
        unit = by_code[code]
        if unit.kind is OrganisationKind.TEAM:
            definitions.append((user, unit, ALL_TEAM_ACTIONS, False, "statistics"))
            continue
        definitions.extend(
            (
                (
                    user,
                    unit,
                    (ManagementAction.STATISTICS,),
                    True,
                    "statistics",
                ),
                (
                    user,
                    unit,
                    (ManagementAction.ROSTER, ManagementAction.CALENDAR),
                    False,
                    "workspace",
                ),
            )
        )
    return definitions
