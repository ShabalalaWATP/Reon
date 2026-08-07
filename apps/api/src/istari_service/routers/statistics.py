"""Authenticated, grant-scoped operational statistics routes."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query

from istari_service.dependencies import CurrentActor, DatabaseSession
from istari_service.repositories.statistics import SqlAlchemyStatisticsRepository
from istari_service.schemas.statistics import StatisticsDashboard, StatisticsScopeList
from istari_service.services.statistics_service import StatisticsService

router = APIRouter(prefix="/statistics", tags=["operational-statistics"])


def _service(session: DatabaseSession) -> StatisticsService:
    return StatisticsService(SqlAlchemyStatisticsRepository(session))


@router.get("/scopes", response_model=StatisticsScopeList)
async def list_statistics_scopes(
    actor: CurrentActor,
    session: DatabaseSession,
) -> StatisticsScopeList:
    return StatisticsScopeList(items=await _service(session).list_scopes(actor))


@router.get("", response_model=StatisticsDashboard)
async def get_statistics(
    actor: CurrentActor,
    session: DatabaseSession,
    scope_id: Annotated[str, Query(alias="scopeId", min_length=1, max_length=80)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    time_zone: Annotated[
        str,
        Query(alias="timeZone", min_length=1, max_length=64),
    ] = "Europe/London",
) -> StatisticsDashboard:
    today = datetime.now(UTC).date()
    return await _service(session).dashboard(
        actor,
        scope_id=scope_id,
        from_date=from_date or today - timedelta(days=89),
        to_date=to_date or today,
        time_zone_name=time_zone,
    )
