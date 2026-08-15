"""Application-facing persistence boundary for personal action projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from mist_service.action_notification_models import (
    ActionProjection,
    ActionSection,
    ActionSourceType,
    ProjectionCheckpoint,
    SavedActionView,
)
from mist_service.domain import Actor
from mist_service.models import UserRole
from mist_service.schemas.actions import (
    ActionFilters,
    SavedActionViewCommand,
    SavedActionViewUpdate,
)


@dataclass(frozen=True, slots=True)
class ActionProjectionCommand:
    """Validated input used to create or refresh one action projection."""

    stable_key: str
    source_type: ActionSourceType
    source_id: str
    source_version: int
    section: ActionSection
    action_type: str
    reference: str
    current_owner: str
    last_changed_at: datetime
    deep_link: str
    projected_at: datetime
    request_id: UUID | None = None
    recipient_user_id: UUID | None = None
    candidate_role: UserRole | None = None
    required_scope: str | None = None
    organisation_unit_id: UUID | None = None
    safe_title: str | None = None
    required_by: date | None = None
    completed_at: datetime | None = None
    is_active: bool = True


class ActionRepositoryPort(Protocol):
    """Operations required by the action workspace use case."""

    async def list_actions(
        self,
        actor: Actor,
        filters: ActionFilters,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[ActionProjection], str | None]: ...

    async def organisation_unit_names(self, unit_ids: set[UUID]) -> dict[UUID, str]: ...

    async def counts(self, actor: Actor) -> dict[ActionSection, int]: ...

    async def saved_views(self, actor: Actor) -> list[SavedActionView]: ...

    async def create_saved_view(
        self, actor: Actor, command: SavedActionViewCommand
    ) -> SavedActionView: ...

    async def update_saved_view(
        self, actor: Actor, view_id: UUID, command: SavedActionViewUpdate
    ) -> SavedActionView: ...

    async def delete_saved_view(
        self, actor: Actor, view_id: UUID, expected_version: int
    ) -> None: ...

    async def project(self, command: ActionProjectionCommand) -> ActionProjection: ...

    async def checkpoint(self, name: str) -> ProjectionCheckpoint | None: ...
