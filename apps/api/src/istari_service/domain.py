"""Persistence-independent records passed through application ports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from istari_service.models import RequestStatus, UserRole, WorkflowTaskStatus


@dataclass(frozen=True, slots=True)
class Actor:
    id: UUID
    username: str
    display_name: str
    role: UserRole
    scope: str


@dataclass(frozen=True, slots=True)
class AccountRecord:
    actor: Actor
    password_hash: str
    is_active: bool
    failed_login_count: int
    locked_until: datetime | None


@dataclass(frozen=True, slots=True)
class SessionRecord:
    id: UUID
    actor: Actor
    csrf_token_hash: str
    expires_at: datetime
    elevated_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class RequestRecord:
    id: UUID
    requester_id: UUID
    status: RequestStatus
    assigned_delivery_team: str | None
    assigned_specialist_id: UUID | None
    version: int


@dataclass(frozen=True, slots=True)
class WorkRecord:
    id: UUID
    request: RequestRecord
    engine_task_key: str | None
    process_instance_key: str
    element_id: str
    task_status: WorkflowTaskStatus
    assignee_id: UUID | None
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ProductDownload:
    reference: str
    text: str
