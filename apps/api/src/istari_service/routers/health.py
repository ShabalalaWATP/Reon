"""Liveness and dependency readiness endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from istari_service.dependencies import ReadinessDatabaseSession, WorkflowDependency

router = APIRouter(tags=["health"])


class ReadinessChecks(BaseModel):
    database: Literal["ok", "unavailable"]
    workflow: Literal["ok", "unavailable"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    session: ReadinessDatabaseSession,
    engine: WorkflowDependency,
) -> ReadinessResponse:
    try:
        await session.execute(text("SELECT 1"))
        database_status: Literal["ok", "unavailable"] = "ok"
    except (OSError, SQLAlchemyError):
        await session.rollback()
        database_status = "unavailable"
    workflow_status: Literal["ok", "unavailable"] = (
        "ok" if await engine.is_reachable() else "unavailable"
    )
    ready = database_status == workflow_status == "ok"
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        checks=ReadinessChecks(
            database=database_status,
            workflow=workflow_status,
        ),
    )
