"""Application-facing notification persistence and projection boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from istari_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
    NotificationEventGroup,
    NotificationPreference,
    NotificationRecipient,
    ProjectionCheckpoint,
)
from istari_service.domain import Actor
from istari_service.models import UserRole
from istari_service.schemas.actions import (
    NotificationFilterState,
    NotificationPreferenceUpdate,
    NotificationStateAction,
    NotificationStateTarget,
)


@dataclass(frozen=True, slots=True)
class RecipientRule:
    """Security context required for one projected notification recipient."""

    user_id: UUID
    access_kind: NotificationAccessKind
    required_role: UserRole
    required_scope: str | None = None
    organisation_unit_id: UUID | None = None


class NotificationRepositoryPort(Protocol):
    """Recipient-owned notification reads, state and preferences."""

    async def list_notifications(
        self,
        actor: Actor,
        *,
        states: list[NotificationFilterState],
        event_types: list[str],
        from_date: datetime | None,
        to_date: datetime | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[tuple[NotificationRecipient, NotificationEvent]], str | None]: ...

    async def unread_count(self, actor: Actor) -> int: ...

    async def mutate_state(
        self,
        actor: Actor,
        action: NotificationStateAction,
        targets: list[NotificationStateTarget],
        *,
        changed_at: datetime,
    ) -> list[tuple[NotificationRecipient, NotificationEvent]]: ...

    async def preferences(self, actor: Actor) -> list[NotificationPreference]: ...

    async def update_preference(
        self,
        actor: Actor,
        event_group: NotificationEventGroup,
        command: NotificationPreferenceUpdate,
    ) -> NotificationPreference: ...

    async def checkpoint(self) -> ProjectionCheckpoint | None: ...


class NotificationProjectionPort(Protocol):
    """Idempotent event publication and recipient materialisation."""

    async def publish_event(
        self,
        *,
        stable_key: str,
        event_type: str,
        event_group: NotificationEventGroup,
        source_version: int,
        request_id: UUID | None,
        safe_subject: str,
        deep_link: str | None,
        audience: list[dict[str, str | None]],
        occurred_at: datetime,
    ) -> NotificationEvent: ...

    async def project_event(
        self,
        event_id: UUID,
        recipients: list[RecipientRule],
        *,
        projected_at: datetime,
        update_checkpoint: bool = True,
    ) -> list[NotificationRecipient]: ...

    async def mark_projection_failed(
        self, event_id: UUID, *, error_code: str, attempted_at: datetime
    ) -> None: ...


class NotificationReconciler(Protocol):
    """Materialise pending outbox events before serving notification reads."""

    async def reconcile_pending(self) -> int: ...
