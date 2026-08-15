"""Bounded records shared by planning ports and pure projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from mist_service.board_models import WorkPackage
from mist_service.planning_analytics_models import PackageBlocker
from mist_service.schemas.planning import PackageChecklistResult


@dataclass(frozen=True, slots=True)
class PackagePlanningRows:
    packages: tuple[tuple[WorkPackage, str], ...]
    iteration_names: dict[UUID, str]
    dependencies: tuple[tuple[UUID, WorkPackage | None], ...]
    blockers: tuple[PackageBlocker, ...]
    checklists: tuple[PackageChecklistResult, ...]


@dataclass(frozen=True, slots=True)
class PlanningFreshnessState:
    rebuilding: bool
    last_projected_at: datetime | None


@dataclass(frozen=True, slots=True)
class ScenarioPreviewRecord:
    token: str
    expires_at: datetime
    source_version: int
