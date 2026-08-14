"""Application service for scoped personal action projections."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from istari_service.action_notification_models import (
    ActionProjection,
    ActionSection,
    ProjectionHealth,
    SavedActionView,
)
from istari_service.action_ports import ActionProjectionCommand, ActionRepositoryPort
from istari_service.domain import Actor
from istari_service.errors import InvalidAction
from istari_service.projection_freshness import projection_freshness
from istari_service.schemas.actions import (
    ActionAccess,
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


class ActionService:
    def __init__(self, repository: ActionRepositoryPort) -> None:
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
        unit_names = await self._repository.organisation_unit_names(
            {
                action.organisation_unit_id
                for action in actions
                if action.organisation_unit_id is not None
            }
        )
        counts = await self._repository.counts(actor)
        views = await self._repository.saved_views(actor)
        checkpoint = await self._repository.checkpoint("actions")
        freshness = projection_freshness(checkpoint, current)
        return ActionWorkspaceResult(
            items=[
                _action_item(item, actor, freshness, current, unit_names)
                for item in actions
            ],
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
        return _saved_view(await self._repository.create_saved_view(actor, command))

    async def update_saved_view(
        self, actor: Actor, view_id: UUID, command: SavedActionViewUpdate
    ) -> SavedActionViewResult:
        return _saved_view(
            await self._repository.update_saved_view(actor, view_id, command)
        )

    async def delete_saved_view(
        self, actor: Actor, view_id: UUID, expected_version: int
    ) -> None:
        await self._repository.delete_saved_view(actor, view_id, expected_version)

    async def project(self, command: ActionProjectionCommand) -> ActionProjection:
        _validate_projection(command)
        return await self._repository.project(command)


def _action_item(
    action: ActionProjection,
    actor: Actor,
    freshness: ProjectionFreshness,
    now: datetime,
    unit_names: dict[UUID, str],
) -> ActionItem:
    changed_at = _utc(action.last_changed_at)
    projected_at = _utc(action.projected_at)
    source_changed_at = freshness.source_changed_at
    stale = freshness.status is not ProjectionHealth.CURRENT or (
        source_changed_at is not None and projected_at < _utc(source_changed_at)
    )
    return ActionItem(
        id=action.id,
        section=action.section,
        action_access=(
            ActionAccess.PERSONAL
            if action.recipient_user_id == actor.id
            else ActionAccess.SHARED
        ),
        action_type=action.action_type,
        source_type=action.source_type,
        reference=action.reference,
        title=action.safe_title,
        current_owner=_current_owner(action, actor, unit_names),
        required_by=action.required_by,
        age_days=max(0, (_utc(now) - changed_at).days),
        last_changed_at=action.last_changed_at,
        deep_link=action.deep_link,
        source_version=action.source_version,
        is_stale=stale,
    )


def _current_owner(
    action: ActionProjection,
    actor: Actor,
    unit_names: dict[UUID, str],
) -> str:
    if action.recipient_user_id == actor.id:
        return actor.display_name
    if action.organisation_unit_id is not None:
        unit_name = unit_names.get(action.organisation_unit_id)
        if unit_name is not None:
            return f"{unit_name} · Awaiting owner"
    return action.current_owner


def _saved_view(view: SavedActionView) -> SavedActionViewResult:
    return SavedActionViewResult(
        id=view.id,
        name=view.name,
        filters=ActionFilters.model_validate(view.filters),
        visible_columns=[ActionColumn(value) for value in view.visible_columns],
        version=view.version,
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


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
