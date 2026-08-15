"""Persistence-independent records passed through application ports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from mist_service.models import (
    IdentityContext,
    RequestStatus,
    UserRole,
    WorkflowTaskStatus,
)


@dataclass(frozen=True, slots=True)
class Actor:
    id: UUID
    username: str
    display_name: str
    role: UserRole
    scope: str
    organisation_unit_ids: frozenset[UUID] = frozenset()


@dataclass(frozen=True, slots=True)
class AccountRecord:
    actor: Actor
    password_hash: str
    is_active: bool
    failed_login_count: int
    locked_until: datetime | None
    customer_context_enabled: bool = False


@dataclass(frozen=True, slots=True)
class SessionRecord:
    id: UUID
    actor: Actor
    csrf_token_hash: str
    expires_at: datetime
    last_seen_at: datetime | None = None
    elevated_until: datetime | None = None
    active_context: IdentityContext = IdentityContext.CUSTOMER
    available_contexts: tuple[IdentityContext, ...] = (IdentityContext.CUSTOMER,)
    context_version: int = 1


@dataclass(frozen=True, slots=True)
class RequestRecord:
    id: UUID
    requester_id: UUID
    status: RequestStatus
    assigned_delivery_team: str | None
    assigned_specialist_id: UUID | None
    version: int
    assigned_delivery_team_id: UUID | None = None
    participant_ids: frozenset[UUID] = frozenset()


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
