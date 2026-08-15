"""Shared, framework-free projection freshness calculation."""

from __future__ import annotations

from datetime import UTC, datetime

from mist_service.action_notification_models import (
    ProjectionCheckpoint,
    ProjectionHealth,
)
from mist_service.schemas.actions import ProjectionFreshness


def projection_freshness(
    checkpoint: ProjectionCheckpoint | None, now: datetime
) -> ProjectionFreshness:
    if checkpoint is None:
        return ProjectionFreshness(
            status=ProjectionHealth.DEGRADED,
            projected_at=None,
            source_changed_at=None,
            lag_seconds=None,
            pending_count=0,
        )
    source = (
        _utc(checkpoint.source_changed_at) if checkpoint.source_changed_at else None
    )
    projected = _utc(checkpoint.projected_at) if checkpoint.projected_at else None
    lag = (
        max(0, int((_utc(now) - source).total_seconds()))
        if source is not None
        else None
    )
    return ProjectionFreshness(
        status=checkpoint.health,
        projected_at=projected,
        source_changed_at=source,
        lag_seconds=lag,
        pending_count=checkpoint.pending_count,
    )


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
