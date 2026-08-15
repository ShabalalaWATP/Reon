"""Focused application ports for content-minimised operational statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from mist_service.domain import Actor
from mist_service.schemas.statistics import StatisticsScope
from mist_service.schemas.statistics_evolution import StatisticsExportCommand
from mist_service.statistics_records import (
    StatisticsDataset,
    StatisticsEvolutionDataset,
)


class StatisticsQueryPort(Protocol):
    """Read authorised aggregate facts without exposing request content."""

    async def list_scopes(self, actor: Actor) -> list[StatisticsScope]: ...

    async def load_dataset(
        self,
        actor: Actor,
        *,
        scope_id: str,
        selected_unit_id: UUID | None,
        start: datetime,
        end: datetime,
        at: datetime,
    ) -> StatisticsDataset: ...


class StatisticsEvolutionQueryPort(Protocol):
    """Read current, comparison and operational aggregate cohorts."""

    async def load(
        self,
        actor: Actor,
        *,
        scope_id: str,
        start: datetime,
        end: datetime,
        previous_start: datetime,
        previous_end: datetime,
        at: datetime,
        selected_unit_id: UUID | None = None,
    ) -> StatisticsEvolutionDataset: ...


class StatisticsExportAuditPort(Protocol):
    """Persist evidence that a requested aggregate export was denied."""

    async def record_denied_export(
        self,
        *,
        actor: Actor,
        command: StatisticsExportCommand,
        scope_unit_id: UUID,
        row_count: int,
        cohort_suppressed: bool,
        reason: str,
    ) -> object: ...
