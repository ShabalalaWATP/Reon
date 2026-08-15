"""Content-free append-only operational fact persistence and scope capture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.analytics_evolution_models import (
    OperationalAnalyticsFact,
    OperationalFactType,
)
from mist_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    RequestRouteSelection,
)

DEFINITION_VERSION = 1
PROJECTION_VERSION = 1


@dataclass(frozen=True, slots=True)
class OperationalScope:
    root_unit_id: UUID
    command_unit_id: UUID | None = None
    ops_unit_id: UUID | None = None
    team_unit_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class OperationalFactInput:
    source_key: str
    type: OperationalFactType
    scope: OperationalScope
    occurred_at: datetime
    count_value: int = 1
    duration_seconds: int | None = None
    measure_minutes: int | None = None


def anonymous_source_key(kind: str, source_id: UUID, discriminator: str) -> str:
    """Return an opaque stable key without copying a domain identifier."""

    digest = sha256(f"{kind}:{source_id}:{discriminator}".encode("ascii")).hexdigest()
    return f"{kind}:{digest}"


async def append_operational_fact(
    session: AsyncSession, fact: OperationalFactInput
) -> bool:
    """Insert once using the production and test databases' conflict primitives."""

    values = {
        "id": uuid4(),
        "source_key": fact.source_key,
        "type": fact.type,
        "root_unit_id": fact.scope.root_unit_id,
        "command_unit_id": fact.scope.command_unit_id,
        "ops_unit_id": fact.scope.ops_unit_id,
        "team_unit_id": fact.scope.team_unit_id,
        "occurred_at": _aware(fact.occurred_at),
        "count_value": fact.count_value,
        "duration_seconds": fact.duration_seconds,
        "measure_minutes": fact.measure_minutes,
        "definition_version": DEFINITION_VERSION,
        "projection_version": PROJECTION_VERSION,
    }
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        statement = (
            postgresql_insert(OperationalAnalyticsFact)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["source_key"])
            .returning(OperationalAnalyticsFact.id)
        )
    elif dialect == "sqlite":
        statement = (
            sqlite_insert(OperationalAnalyticsFact)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["source_key"])
            .returning(OperationalAnalyticsFact.id)
        )
    else:
        raise RuntimeError("operational analytics requires PostgreSQL or SQLite")
    return (await session.execute(statement)).scalar_one_or_none() is not None


async def request_operational_scope(
    session: AsyncSession, request_id: UUID
) -> OperationalScope | None:
    rows = (
        await session.execute(
            select(RequestRouteSelection.position, RequestRouteSelection.unit_id)
            .where(RequestRouteSelection.request_id == request_id)
            .order_by(RequestRouteSelection.position)
        )
    ).all()
    route: dict[int, UUID] = {}
    for position, unit_id in rows:
        route[position] = unit_id
    root = route.get(0)
    if root is None:
        return None
    return OperationalScope(
        root_unit_id=root,
        command_unit_id=route.get(1),
        ops_unit_id=route.get(2),
        team_unit_id=route.get(3),
    )


async def unit_operational_scope(
    session: AsyncSession, unit_id: UUID
) -> OperationalScope | None:
    values: dict[OrganisationKind, UUID] = {}
    current_id: UUID | None = unit_id
    visited: set[UUID] = set()
    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        unit = await session.get(OrganisationUnit, current_id)
        if unit is None:
            return None
        values[unit.kind] = unit.id
        current_id = unit.parent_id
    root = values.get(OrganisationKind.ROOT)
    if root is None or current_id in visited:
        return None
    return OperationalScope(
        root_unit_id=root,
        command_unit_id=values.get(OrganisationKind.COMMAND),
        ops_unit_id=values.get(OrganisationKind.OPS_GROUP),
        team_unit_id=values.get(OrganisationKind.TEAM),
    )


def elapsed_seconds(start: datetime, end: datetime) -> int:
    return max(0, int((_aware(end) - _aware(start)).total_seconds()))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
