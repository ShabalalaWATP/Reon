"""Liveness and dependency readiness endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from istari_service.configuration_readiness import configuration_runtime_is_ready
from istari_service.dependencies import (
    AppSettings,
    ReadinessDatabaseSession,
    WorkflowDependency,
)
from istari_service.repositories.maintenance_leases import (
    SqlAlchemyMaintenanceLeaseRepository,
)

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
    try:
        await session.execute(text("SELECT 1"))
        database_status: Literal["ok", "unavailable"] = "ok"
        configuration_status: Literal["ok", "unavailable"] = (
            "ok" if await configuration_runtime_is_ready(session) else "unavailable"
        )
        worker_fresh = not settings.worker_health_required or (
            await SqlAlchemyMaintenanceLeaseRepository(session).heartbeat_is_fresh(
                now=datetime.now(UTC),
                maximum_age_seconds=settings.worker_heartbeat_stale_seconds,
            )
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        database_status = "unavailable"
        configuration_status = "unavailable"
        worker_fresh = False
    workflow_status: Literal["ok", "unavailable"] = (
        "ok" if await engine.is_reachable() else "unavailable"
    )
    maintenance_status: Literal["ok", "unavailable", "disabled"] = (
        "disabled"
        if not settings.worker_health_required
        else ("ok" if worker_fresh else "unavailable")
    )
    ready = (
        database_status == workflow_status == "ok"
        and configuration_status == "ok"
        and maintenance_status != "unavailable"
    )
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        checks=ReadinessChecks(
            database=database_status,
            workflow=workflow_status,
            configuration=configuration_status,
            maintenance=maintenance_status,
        ),
    )
