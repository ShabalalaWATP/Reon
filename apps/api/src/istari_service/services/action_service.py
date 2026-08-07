"""Application service for scoped personal action projections."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from istari_service.action_notification_models import (
    ActionProjection,
    ActionSection,
    ActionSourceType,
    ProjectionCheckpoint,
    ProjectionHealth,
    SavedActionView,
)
from istari_service.domain import Actor
from istari_service.errors import InvalidAction
from istari_service.models import UserRole
from istari_service.repositories.actions import SqlAlchemyActionRepository, utc
from istari_service.schemas.actions import (
    ActionColumn,
    ActionCounts,
    ActionFilters,
    ActionItem,
    ActionWorkspaceResult,
    ProjectionFreshness,
    SavedActionViewCommand,
    SavedActionViewResult,
    SavedActionViewUpdate,
)

ACTION_TYPE = re.compile(r"[A-Z][A-Z0-9_]{0,79}")


@dataclass(frozen=True, slots=True)
class ActionProjectionCommand:
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


class ActionService:
    def __init__(self, repository: SqlAlchemyActionRepository) -> None:
        self._repository = repository

    async def workspace(
        self,
        actor: Actor,
        filters: ActionFilters,
        *,
        limit: int,
        cursor: str | None,
        now: datetime | None = None,
    ) -> ActionWorkspaceResult:
        current = now or datetime.now(UTC)
        actions, next_cursor = await self._repository.list_actions(
            actor, filters, limit=limit, cursor=cursor
        )
        counts = await self._repository.counts(actor)
        views = await self._repository.saved_views(actor.id)
        checkpoint = await self._repository.checkpoint("actions")
        freshness = _freshness(checkpoint, current)
        return ActionWorkspaceResult(
            items=[_action_item(item, freshness, current) for item in actions],
            counts=ActionCounts(
                needs_my_action=counts.get(ActionSection.NEEDS_MY_ACTION, 0),
                waiting=counts.get(ActionSection.WAITING, 0),
                due_soon=counts.get(ActionSection.DUE_SOON, 0),
                recently_completed=counts.get(ActionSection.RECENTLY_COMPLETED, 0),
            ),
            saved_views=[_saved_view(view) for view in views],
            next_cursor=next_cursor,
            freshness=freshness,
        )

    async def create_saved_view(
        self, actor: Actor, command: SavedActionViewCommand
    ) -> SavedActionViewResult:
        return _saved_view(await self._repository.create_saved_view(actor.id, command))

    async def update_saved_view(
        self, actor: Actor, view_id: UUID, command: SavedActionViewUpdate
    ) -> SavedActionViewResult:
        return _saved_view(
            await self._repository.update_saved_view(actor.id, view_id, command)
        )

    async def delete_saved_view(
        self, actor: Actor, view_id: UUID, expected_version: int
    ) -> None:
        await self._repository.delete_saved_view(actor.id, view_id, expected_version)

    async def project(self, command: ActionProjectionCommand) -> ActionProjection:
        _validate_projection(command)
        return await self._repository.project_action(**asdict(command))


def _action_item(
    action: ActionProjection,
    freshness: ProjectionFreshness,
    now: datetime,
) -> ActionItem:
    changed_at = utc(action.last_changed_at)
    projected_at = utc(action.projected_at)
    source_changed_at = freshness.source_changed_at
    stale = freshness.status is not ProjectionHealth.CURRENT or (
        source_changed_at is not None and projected_at < utc(source_changed_at)
    )
    return ActionItem(
        id=action.id,
        section=action.section,
        action_type=action.action_type,
        source_type=action.source_type,
        reference=action.reference,
        title=action.safe_title,
        current_owner=action.current_owner,
        required_by=action.required_by,
        age_days=max(0, (utc(now) - changed_at).days),
        last_changed_at=action.last_changed_at,
        deep_link=action.deep_link,
        source_version=action.source_version,
        is_stale=stale,
    )


def _saved_view(view: SavedActionView) -> SavedActionViewResult:
    return SavedActionViewResult(
        id=view.id,
        name=view.name,
        filters=ActionFilters.model_validate(view.filters),
        visible_columns=[ActionColumn(value) for value in view.visible_columns],
        version=view.version,
    )


def _freshness(
    checkpoint: ProjectionCheckpoint | None, now: datetime
) -> ProjectionFreshness:
    if checkpoint is None:
        return ProjectionFreshness(
            status=ProjectionHealth.DEGRADED,
            projected_at=None,
            source_changed_at=None,
            lag_seconds=None,
            pending_count=0,
        )
    source = utc(checkpoint.source_changed_at) if checkpoint.source_changed_at else None
    projected = utc(checkpoint.projected_at) if checkpoint.projected_at else None
    lag = (
        max(0, int((utc(now) - source).total_seconds())) if source is not None else None
    )
    return ProjectionFreshness(
        status=checkpoint.health,
        projected_at=projected,
        source_changed_at=source,
        lag_seconds=lag,
        pending_count=checkpoint.pending_count,
    )


def _validate_projection(command: ActionProjectionCommand) -> None:
    if command.source_version < 1:
        raise InvalidAction("An action source version must be positive.")
    if not command.stable_key.strip() or len(command.stable_key) > 160:
        raise InvalidAction("An action projection key is invalid.")
    if ACTION_TYPE.fullmatch(command.action_type.strip().upper()) is None:
        raise InvalidAction("An action type is invalid.")
    if command.recipient_user_id is None and command.candidate_role is None:
        raise InvalidAction("An action audience is required.")
    if command.organisation_unit_id is not None and command.candidate_role is None:
        raise InvalidAction("An organisation action requires a role audience.")
    if command.required_scope is not None and command.candidate_role is None:
        raise InvalidAction("A scoped action requires a role audience.")
    if (
        not command.deep_link.startswith("/")
        or command.deep_link.startswith("//")
        or "\\" in command.deep_link
        or any(char in command.deep_link for char in "\r\n")
    ):
        raise InvalidAction("An action link must be application-local.")
