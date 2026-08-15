"""Projection checkpoint persistence for notification materialisation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.action_notification_models import (
    NotificationEvent,
    NotificationProjectionStatus,
    ProjectionCheckpoint,
    ProjectionHealth,
)


async def update_notification_checkpoint(
    session: AsyncSession,
    event: NotificationEvent,
    projected_at: datetime,
    *,
    failed: bool,
) -> None:
    checkpoint = await session.get(ProjectionCheckpoint, "notifications")
    if checkpoint is None:
        checkpoint = ProjectionCheckpoint(name="notifications")
        session.add(checkpoint)
    checkpoint.last_event_key = event.stable_key
    checkpoint.source_changed_at = event.occurred_at
    checkpoint.projected_at = projected_at
    checkpoint.pending_count = await _status_count(
        session, NotificationProjectionStatus.PENDING
    )
    checkpoint.failed_count = await _status_count(
        session, NotificationProjectionStatus.FAILED
    )
    checkpoint.health = (
        ProjectionHealth.DEGRADED
        if failed or checkpoint.failed_count
        else ProjectionHealth.CURRENT
    )


async def _status_count(
    session: AsyncSession, status: NotificationProjectionStatus
) -> int:
    return int(
        await session.scalar(
            select(func.count(NotificationEvent.id)).where(
                NotificationEvent.status == status
            )
        )
        or 0
    )
