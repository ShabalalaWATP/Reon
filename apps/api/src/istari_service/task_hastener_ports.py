"""Narrow boundaries and immutable records for the task-hastener use case."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from istari_service.models import RequestStatus
from istari_service.organisation_models import OrganisationKind
from istari_service.request_participant_models import RequestParticipantRole
from istari_service.team_models import WorkspacePosition


@dataclass(frozen=True, slots=True)
class TaskHastenerRequestRecord:
    id: UUID
    requester_id: UUID
    status: RequestStatus
    reference: str


@dataclass(frozen=True, slots=True)
class TaskHastenerRecipientRecord:
    user_id: UUID
    display_name: str
    assignment_role: RequestParticipantRole


@dataclass(frozen=True, slots=True)
class TaskHastenerWorkspaceRecord:
    unit_kind: OrganisationKind
    workspace_position: WorkspacePosition | None


@dataclass(frozen=True, slots=True)
class TaskHastenerEventRecord:
    id: UUID
    event_hash: str
    source_version: int
    created_at: datetime


class TaskHastenerRequestReader(Protocol):
    async def request_for_team(
        self, team_id: UUID, request_id: UUID
    ) -> TaskHastenerRequestRecord | None: ...

    async def active_recipients(
        self, team_id: UUID, request_id: UUID
    ) -> list[TaskHastenerRecipientRecord]: ...


class TaskHastenerWorkspaceReader(Protocol):
    async def require_read(
        self, actor_id: UUID, team_id: UUID
    ) -> TaskHastenerWorkspaceRecord: ...


class TaskHastenerEventWriter(Protocol):
    async def append(
        self,
        *,
        request: TaskHastenerRequestRecord,
        actor_id: UUID,
        message: str,
        recipient_ids: list[UUID],
        audience: str,
    ) -> TaskHastenerEventRecord: ...


class TaskHastenerNotifier(Protocol):
    async def notify(
        self,
        *,
        request: TaskHastenerRequestRecord,
        team_id: UUID,
        event: TaskHastenerEventRecord,
        recipients: list[TaskHastenerRecipientRecord],
    ) -> frozenset[UUID]: ...
