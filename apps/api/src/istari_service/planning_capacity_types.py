"""Framework-free records for aggregate planning capacity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PlanningCapacityDay:
    date: date
    baseline_minutes: int
    calendar_minutes: int
    reserved_minutes: int
    available_minutes: int


@dataclass(frozen=True, slots=True)
class PlanningCapacityProjection:
    days: tuple[PlanningCapacityDay, ...]
    source_digest: str

    @property
    def available_minutes(self) -> int:
        return sum(day.available_minutes for day in self.days)

    @property
    def reserved_minutes(self) -> int:
        return sum(day.reserved_minutes for day in self.days)
