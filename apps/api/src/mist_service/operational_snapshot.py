"""Content-free database health snapshot and deterministic alert evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from mist_service.analytics_models import AnalyticsProjectionState, ProjectionHealth
from mist_service.models import (
    Base,
    OutboxStatus,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
    WorkflowTask,
    WorkflowTaskStatus,
)
from mist_service.operations_models import OperationalRun


@dataclass(frozen=True)
class OperationalSnapshot:
    captured_at: datetime
    command_backlog: int
    failed_commands: int
    oldest_command_age_seconds: int
    workflow_instance_errors: int
    workflow_task_errors: int
    projection_health: str
    projection_age_seconds: int | None
    retention_age_seconds: int | None
    alerts: tuple[str, ...]

    @property
    def status(self) -> str:
        return "warning" if self.alerts else "ok"


async def capture_operational_snapshot(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    max_command_age_seconds: int = 300,
    max_projection_age_seconds: int = 600,
) -> OperationalSnapshot:
    captured = now or datetime.now(UTC)
    actionable = [OutboxStatus.PENDING, OutboxStatus.PROCESSING, OutboxStatus.FAILED]
    command_backlog = await _count(
        session, WorkflowOutbox, WorkflowOutbox.status.in_(actionable)
    )
    failed_commands = await _count(
        session, WorkflowOutbox, WorkflowOutbox.status == OutboxStatus.FAILED
    )
    oldest = await session.scalar(
        select(func.min(WorkflowOutbox.available_at)).where(
            WorkflowOutbox.status.in_(actionable)
        )
    )
    projection = await session.scalar(select(AnalyticsProjectionState))
    last_retention = await session.scalar(
        select(func.max(OperationalRun.created_at)).where(
            OperationalRun.job_name == "retention",
            OperationalRun.mode == "APPLIED",
        )
    )
    command_age = _age(captured, oldest) or 0
    projection_age = _age(
        captured, projection.last_projected_at if projection else None
    )
    alerts: list[str] = []
    if failed_commands:
        alerts.append("failed_workflow_commands")
    if command_age > max_command_age_seconds:
        alerts.append("workflow_command_backlog_old")
    if projection is None or projection.health is not ProjectionHealth.READY:
        alerts.append("analytics_projection_not_ready")
    elif projection_age is not None and projection_age > max_projection_age_seconds:
        alerts.append("analytics_projection_stale")
    instance_errors = await _count(
        session,
        WorkflowInstance,
        WorkflowInstance.status == WorkflowInstanceStatus.ERROR,
    )
    task_errors = await _count(
        session, WorkflowTask, WorkflowTask.status == WorkflowTaskStatus.ERROR
    )
    if instance_errors or task_errors:
        alerts.append("workflow_projection_errors")
    return OperationalSnapshot(
        captured_at=captured,
        command_backlog=command_backlog,
        failed_commands=failed_commands,
        oldest_command_age_seconds=command_age,
        workflow_instance_errors=instance_errors,
        workflow_task_errors=task_errors,
        projection_health=projection.health.value if projection else "MISSING",
        projection_age_seconds=projection_age,
        retention_age_seconds=_age(captured, last_retention),
        alerts=tuple(alerts),
    )


async def _count(
    session: AsyncSession,
    model: type[Base],
    condition: ColumnElement[bool],
) -> int:
    result = await session.execute(
        select(func.count()).select_from(model).where(condition)
    )
    return int(result.scalar_one())


def _age(now: datetime, value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return max(0, int((now - value).total_seconds()))
