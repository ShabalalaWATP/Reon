"""Enhanced content-free operational statistics and export routes."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from mist_service.dependencies import (
    CurrentActor,
    DatabaseSession,
    MutationActor,
)
from mist_service.schemas.statistics_evolution import (
    StatisticsEvolution,
    StatisticsExportCommand,
    StatisticsExportResult,
)
from mist_service.services.statistics_evolution_service import (
    StatisticsEvolutionService,
)
from mist_service.statistics_composition import statistics_evolution_service

router = APIRouter(tags=["operational-statistics"])


def _service(session: DatabaseSession) -> StatisticsEvolutionService:
    return statistics_evolution_service(session)


@router.get("/evolution", response_model=StatisticsEvolution)
async def get_statistics_evolution(
    actor: CurrentActor,
    session: DatabaseSession,
    scope_id: Annotated[str, Query(alias="scopeId", min_length=1, max_length=80)],
    unit_id: Annotated[UUID | None, Query(alias="unitId")] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    time_zone: Annotated[
        str,
        Query(alias="timeZone", min_length=1, max_length=64),
    ] = "Europe/London",
) -> StatisticsEvolution:
    today = datetime.now(UTC).date()
    return await _service(session).dashboard(
        actor,
        scope_id=scope_id,
        selected_unit_id=unit_id,
        from_date=from_date or today - timedelta(days=89),
        to_date=to_date or today,
        time_zone_name=time_zone,
    )


@router.post("/exports", response_model=StatisticsExportResult)
async def request_statistics_export(
    command: StatisticsExportCommand,
    actor: MutationActor,
    session: DatabaseSession,
) -> StatisticsExportResult:
    return await _service(session).request_export(actor, command)
