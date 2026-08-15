"""Stable, public-safe organisation configuration."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    StaffingStatus,
)

ORGANISATION_NAMESPACE = UUID("8875787d-2850-4dc9-948b-d526082032de")


def organisation_id(code: str) -> UUID:
    return uuid5(ORGANISATION_NAMESPACE, code)


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    code: str
    name: str
    kind: OrganisationKind
    parent_code: str | None
    staffing_status: StaffingStatus
    routing_group: str | None = None
    manager_group: str | None = None
    analyst_group: str | None = None


TREE = (
    (
        "JOCK",
        (
            (
                "ACSA_B_OPS",
                "ACSA-B Ops",
                (
                    ("SSG_TEAM", "SSG Team"),
                    ("CEDAR_TEAM", "Cedar Team"),
                    ("QUARTZ_TEAM", "Quartz Team"),
                ),
            ),
            (
                "AURORA_OPS",
                "Aurora Ops",
                (
                    ("LANTERN_TEAM", "Lantern Team"),
                    ("MOSAIC_TEAM", "Mosaic Team"),
                    ("COMPASS_TEAM", "Compass Team"),
                ),
            ),
            (
                "VERTEX_OPS",
                "Vertex Ops",
                (
                    ("EMBER_TEAM", "Ember Team"),
                    ("ATLAS_TEAM", "Atlas Team"),
                    ("HARBOUR_TEAM", "Harbour Team"),
                ),
            ),
        ),
    ),
    (
        "SYGOC",
        (
            (
                "NIMBUS_OPS",
                "Nimbus Ops",
                (
                    ("BEACON_TEAM", "Beacon Team"),
                    ("SLATE_TEAM", "Slate Team"),
                    ("ORCHARD_TEAM", "Orchard Team"),
                ),
            ),
            (
                "PARALLAX_OPS",
                "Parallax Ops",
                (
                    ("LUMEN_TEAM", "Lumen Team"),
                    ("NORTHSTAR_TEAM", "Northstar Team"),
                    ("COPPER_TEAM", "Copper Team"),
                ),
            ),
            (
                "HORIZON_OPS",
                "Horizon Ops",
                (
                    ("ROWAN_TEAM", "Rowan Team"),
                    ("VELA_TEAM", "Vela Team"),
                    ("KEEL_TEAM", "Keel Team"),
                ),
            ),
        ),
    ),
    (
        "MYGOC",
        (
            (
                "MERIDIAN_OPS",
                "Meridian Ops",
                (
                    ("FLINT_TEAM", "Flint Team"),
                    ("THISTLE_TEAM", "Thistle Team"),
                    ("GRANITE_TEAM", "Granite Team"),
                ),
            ),
            (
                "SOLSTICE_OPS",
                "Solstice Ops",
                (
                    ("KESTREL_TEAM", "Kestrel Team"),
                    ("JUNIPER_TEAM", "Juniper Team"),
                    ("VALE_TEAM", "Vale Team"),
                ),
            ),
            (
                "FRONTIER_OPS",
                "Frontier Ops",
                (
                    ("TIDAL_TEAM", "Tidal Team"),
                    ("GROVE_TEAM", "Grove Team"),
                    ("PRISM_TEAM", "Prism Team"),
                ),
            ),
        ),
    ),
)


def _group_slug(code: str) -> str:
    return code.lower().replace("_", "-")


def _unit_definitions() -> tuple[UnitDefinition, ...]:
    definitions = [
        UnitDefinition(
            "CRIOC",
            "CRIOC",
            OrganisationKind.ROOT,
            None,
            StaffingStatus.ROUTING_POOL,
            routing_group="crioc-routing",
        )
    ]
    for command_code, ops_groups in TREE:
        definitions.append(
            UnitDefinition(
                command_code,
                command_code,
                OrganisationKind.COMMAND,
                "CRIOC",
                StaffingStatus.ROUTING_POOL,
                routing_group=f"{_group_slug(command_code)}-routing",
            )
        )
        for ops_code, ops_name, teams in ops_groups:
            definitions.append(
                UnitDefinition(
                    ops_code,
                    ops_name,
                    OrganisationKind.OPS_GROUP,
                    command_code,
                    StaffingStatus.ROUTING_POOL,
                    routing_group=f"{_group_slug(ops_code)}-routing",
                )
            )
            for team_code, team_name in teams:
                slug = _group_slug(team_code)
                definitions.append(
                    UnitDefinition(
                        team_code,
                        team_name,
                        OrganisationKind.TEAM,
                        ops_code,
                        StaffingStatus.STAFFED,
                        manager_group=f"{slug}-managers",
                        analyst_group=f"{slug}-analysts",
                    )
                )
    return tuple(definitions)


UNIT_DEFINITIONS = _unit_definitions()
QC_UNIT_DEFINITION = UnitDefinition(
    "QC_TEAM",
    "Combined QC Team",
    OrganisationKind.TEAM,
    "CRIOC",
    StaffingStatus.STAFFED,
    manager_group="qc-team-managers",
    analyst_group="qc-team-members",
)


async def seed_organisation_units(session: AsyncSession) -> int:
    existing = {
        unit.code: unit
        for unit in (await session.scalars(select(OrganisationUnit))).all()
    }
    for stored_unit in existing.values():
        stored_unit.is_configured = False
    created = 0
    for sort_order, definition in enumerate(UNIT_DEFINITIONS):
        parent = existing.get(definition.parent_code or "")
        configured = existing.get(definition.code)
        is_new = configured is None
        if configured is None:
            configured = OrganisationUnit(
                id=organisation_id(definition.code),
                code=definition.code,
                name=definition.name,
            )
            session.add(configured)
            existing[definition.code] = configured
            created += 1
        configured.kind = definition.kind
        configured.parent_id = parent.id if parent else None
        if is_new or definition.kind is not OrganisationKind.TEAM:
            configured.staffing_status = definition.staffing_status
        configured.routing_candidate_group = definition.routing_group
        configured.manager_candidate_group = definition.manager_group
        configured.analyst_candidate_group = definition.analyst_group
        configured.sort_order = sort_order
        configured.is_configured = True
        await session.flush()
    definition = QC_UNIT_DEFINITION
    qc_team = existing.get(definition.code)
    if qc_team is None:
        qc_team = OrganisationUnit(
            id=organisation_id(definition.code),
            code=definition.code,
            name=definition.name,
        )
        session.add(qc_team)
        created += 1
    qc_team.kind = definition.kind
    qc_team.parent_id = existing["CRIOC"].id
    qc_team.staffing_status = definition.staffing_status
    qc_team.routing_candidate_group = None
    qc_team.manager_candidate_group = definition.manager_group
    qc_team.analyst_candidate_group = definition.analyst_group
    qc_team.sort_order = len(UNIT_DEFINITIONS)
    qc_team.is_configured = False
    await session.flush()
    from mist_service.repositories.management import rebuild_organisation_closure

    await rebuild_organisation_closure(session)
    return created
