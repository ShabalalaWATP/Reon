"""Content-minimised planning events exposed through a narrow publisher port."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class PlanningEventType(StrEnum):
    ASSIGNMENT_CHANGED = "ASSIGNMENT_CHANGED"
    BLOCKER_OPENED = "BLOCKER_OPENED"
    BLOCKER_RESOLVED = "BLOCKER_RESOLVED"
    DUE_RISK_CHANGED = "DUE_RISK_CHANGED"
    ITERATION_CHANGED = "ITERATION_CHANGED"
    CAPACITY_COMMITTED = "CAPACITY_COMMITTED"


class PlanningSubjectKind(StrEnum):
    REQUEST = "REQUEST"
    PACKAGE = "PACKAGE"
    ITERATION = "ITERATION"
    TEAM = "TEAM"


@dataclass(frozen=True, slots=True)
class PlanningDomainEvent:
    """A content-free signal, never a copy of package or request text."""

    type: PlanningEventType
    subject_kind: PlanningSubjectKind
    subject_id: UUID
    team_id: UUID
    actor_user_id: UUID
    occurred_at: datetime
    source_version: int
    target_user_id: UUID | None = None


class PlanningEventPublisher(Protocol):
    async def publish(self, event: PlanningDomainEvent) -> None:
        """Persist or enqueue the event in the caller's unit of work."""


class NullPlanningEventPublisher:
    async def publish(self, event: PlanningDomainEvent) -> None:
        del event
