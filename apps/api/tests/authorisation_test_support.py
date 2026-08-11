"""Shared builders for typed authorisation policy tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from istari_service.domain import Actor, RequestRecord, WorkRecord
from istari_service.models import RequestStatus, UserRole, WorkflowTaskStatus


def actor(
    role: UserRole,
    *,
    user_id: UUID | None = None,
    scope: str = "CRIOC",
    units: frozenset[UUID] = frozenset(),
) -> Actor:
    return Actor(
        user_id or uuid4(),
        f"{role.value.lower()}@example.test",
        "Synthetic User",
        role,
        scope,
        units,
    )


def request(
    owner: Actor,
    *,
    status: RequestStatus = RequestStatus.TRIAGE_REVIEW,
    team: str | None = None,
    team_id: UUID | None = None,
    specialist_id: UUID | None = None,
    participants: frozenset[UUID] = frozenset(),
) -> RequestRecord:
    return RequestRecord(
        uuid4(),
        owner.id,
        status,
        team,
        specialist_id,
        1,
        team_id,
        participants,
    )


def work(
    record: RequestRecord,
    *,
    task_status: WorkflowTaskStatus = WorkflowTaskStatus.OPEN,
    assignee_id: UUID | None = None,
    completed: bool = False,
) -> WorkRecord:
    return WorkRecord(
        uuid4(),
        record,
        "task-key",
        "process-key",
        "synthetic-element",
        task_status,
        assignee_id,
        datetime.now(UTC) if completed else None,
    )
