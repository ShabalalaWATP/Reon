"""Liveness and dependency readiness endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from mist_service.dependencies import (
    AppSettings,
    ReadinessDatabaseSession,
    WorkflowDependency,
)
from mist_service.health_composition import check_persistence_readiness

router = APIRouter(tags=["health"])


class ReadinessChecks(BaseModel):
    database: Literal["ok", "unavailable"]
    workflow: Literal["ok", "unavailable"]
    configuration: Literal["ok", "unavailable"]
    maintenance: Literal["ok", "unavailable", "disabled"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=ReadinessResponse, include_in_schema=False)
async def readiness(
    response: Response,
    session: ReadinessDatabaseSession,
    engine: WorkflowDependency,
    settings: AppSettings,
) -> ReadinessResponse:
    persistence = await check_persistence_readiness(
        session,
        worker_health_required=settings.worker_health_required,
        worker_heartbeat_stale_seconds=settings.worker_heartbeat_stale_seconds,
        now=datetime.now(UTC),
    )
    workflow_status: Literal["ok", "unavailable"] = (
        "ok" if await engine.is_reachable() else "unavailable"
    )
    maintenance_status: Literal["ok", "unavailable", "disabled"] = (
        "disabled"
        if not settings.worker_health_required
        else ("ok" if persistence.worker_fresh else "unavailable")
    )
    ready = (
        persistence.database == workflow_status == "ok"
        and persistence.configuration == "ok"
        and maintenance_status != "unavailable"
    )
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        checks=ReadinessChecks(
            database=persistence.database,
            workflow=workflow_status,
            configuration=persistence.configuration,
            maintenance=maintenance_status,
        ),
    )
