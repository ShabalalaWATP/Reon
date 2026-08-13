"""Scoped persistence for the personal action workspace."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import (
    ActionProjection,
    ActionSection,
    ActionSourceType,
    ProjectionCheckpoint,
    ProjectionHealth,
    SavedActionView,
)
from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound, StaleVersion
from istari_service.models import User, UserRole
from istari_service.organisation_models import OrganisationUnit
from istari_service.repositories.action_scope import (
    candidate_access,
    direct_request_access,
)
from istari_service.repositories.projection_pagination import (
    decode_cursor,
    encode_cursor,
)
from istari_service.schemas.actions import (
    ActionFilters,
    SavedActionViewCommand,
    SavedActionViewUpdate,
)


class SqlAlchemyActionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_actions(
        self,
        actor: Actor,
        filters: ActionFilters,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[ActionProjection], str | None]:
        await self._require_current_actor(actor)
        query = self._visible_query(actor)
        if filters.sections:
            query = query.where(ActionProjection.section.in_(filters.sections))
        if filters.action_types:
            query = query.where(ActionProjection.action_type.in_(filters.action_types))
        if filters.due_before is not None:
            query = query.where(ActionProjection.required_by <= filters.due_before)
        if cursor is not None:
            changed_at, item_id = decode_cursor(
                cursor, message="The action filters are invalid."
            )
            query = query.where(
                or_(
                    ActionProjection.last_changed_at < changed_at,
                    and_(
                        ActionProjection.last_changed_at == changed_at,
                        ActionProjection.id < item_id,
                    ),
                )
            )
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(
                        ActionProjection.last_changed_at.desc(),
                        ActionProjection.id.desc(),
                    ).limit(limit + 1)
                )
            ).all()
        )
        if len(rows) <= limit:
            return rows, None
        last = rows[limit - 1]
        return rows[:limit], encode_cursor(last.last_changed_at, last.id)

    async def counts(self, actor: Actor) -> dict[ActionSection, int]:
        await self._require_current_actor(actor)
        rows = (
            (
                await self.session.execute(
                    self._visible_query(actor)
                    .with_only_columns(ActionProjection.section, func.count())
                    .group_by(ActionProjection.section)
                )
            )
            .tuples()
            .all()
        )
        return dict(rows)

    async def organisation_unit_names(self, unit_ids: set[UUID]) -> dict[UUID, str]:
        if not unit_ids:
            return {}
        rows = await self.session.execute(
            select(OrganisationUnit.id, OrganisationUnit.name).where(
                OrganisationUnit.id.in_(unit_ids)
            )
        )
        return dict(rows.tuples().all())

    async def saved_views(self, actor_id: UUID) -> list[SavedActionView]:
        return list(
            (
                await self.session.scalars(
                    select(SavedActionView)
                    .where(SavedActionView.owner_user_id == actor_id)
                    .order_by(SavedActionView.name, SavedActionView.id)
                )
            ).all()
        )

    async def create_saved_view(
        self, actor_id: UUID, command: SavedActionViewCommand
    ) -> SavedActionView:
        view = SavedActionView(
            owner_user_id=actor_id,
            name=command.name.strip(),
            filters=command.filters.model_dump(mode="json"),
            visible_columns=[column.value for column in command.visible_columns],
            version=1,
        )
        self.session.add(view)
        await self.session.flush()
        return view

    async def update_saved_view(
        self, actor_id: UUID, view_id: UUID, command: SavedActionViewUpdate
    ) -> SavedActionView:
        view = await self._locked_view(actor_id, view_id)
        if view.version != command.expected_version:
            raise StaleVersion()
        view.name = command.name.strip()
        view.filters = command.filters.model_dump(mode="json")
        view.visible_columns = [column.value for column in command.visible_columns]
        view.version += 1
        return view

    async def delete_saved_view(
        self, actor_id: UUID, view_id: UUID, expected_version: int
    ) -> None:
        view = await self._locked_view(actor_id, view_id)
        if view.version != expected_version:
            raise StaleVersion()
        await self.session.delete(view)

    async def project_action(
        self,
        *,
        stable_key: str,
        source_type: ActionSourceType,
        source_id: str,
        source_version: int,
        request_id: UUID | None,
        recipient_user_id: UUID | None,
        candidate_role: UserRole | None,
        required_scope: str | None,
        organisation_unit_id: UUID | None,
        section: ActionSection,
        action_type: str,
        reference: str,
        safe_title: str | None,
        current_owner: str,
        required_by: date | None,
        last_changed_at: datetime,
        completed_at: datetime | None,
        deep_link: str,
        projected_at: datetime,
        is_active: bool = True,
    ) -> ActionProjection:
        action = await self.session.scalar(
            select(ActionProjection)
            .where(ActionProjection.stable_key == stable_key)
            .with_for_update()
        )
        if action is not None and action.source_version >= source_version:
            return action
        values = {
            "source_type": source_type,
            "source_id": source_id,
            "source_version": source_version,
            "request_id": request_id,
            "recipient_user_id": recipient_user_id,
            "candidate_role": candidate_role,
            "required_scope": required_scope,
            "organisation_unit_id": organisation_unit_id,
            "section": section,
            "action_type": action_type.strip().upper(),
            "reference": reference.strip(),
            "safe_title": safe_title.strip() if safe_title else None,
            "current_owner": current_owner.strip(),
            "required_by": required_by,
            "last_changed_at": last_changed_at,
            "completed_at": completed_at,
            "deep_link": deep_link,
            "projected_at": projected_at,
            "is_active": is_active,
        }
        if action is None:
            action = ActionProjection(stable_key=stable_key, version=1, **values)
            self.session.add(action)
        else:
            for name, value in values.items():
                setattr(action, name, value)
            action.version += 1
        await self.session.flush()
        return action

    async def checkpoint(self, name: str) -> ProjectionCheckpoint | None:
        return await self.session.get(ProjectionCheckpoint, name)

    async def update_checkpoint(
        self,
        name: str,
        *,
        last_event_key: str | None,
        source_changed_at: datetime | None,
        projected_at: datetime | None,
        pending_count: int,
        failed_count: int,
        health: ProjectionHealth,
    ) -> ProjectionCheckpoint:
        checkpoint = await self.session.get(ProjectionCheckpoint, name)
        if checkpoint is None:
            checkpoint = ProjectionCheckpoint(name=name)
            self.session.add(checkpoint)
        checkpoint.last_event_key = last_event_key
        checkpoint.source_changed_at = source_changed_at
        checkpoint.projected_at = projected_at
        checkpoint.pending_count = pending_count
        checkpoint.failed_count = failed_count
        checkpoint.health = health
        await self.session.flush()
        return checkpoint

    async def _locked_view(self, actor_id: UUID, view_id: UUID) -> SavedActionView:
        view = await self.session.scalar(
            select(SavedActionView)
            .where(
                SavedActionView.id == view_id,
                SavedActionView.owner_user_id == actor_id,
            )
            .with_for_update()
        )
        if view is None:
            raise ObjectNotFound()
        return view

    async def _require_current_actor(self, actor: Actor) -> None:
        current = await self.session.scalar(
            select(User.id).where(
                User.id == actor.id,
                User.is_active.is_(True),
                User.role == actor.role,
                User.scope == actor.scope,
            )
        )
        if current is None:
            raise ObjectNotFound()

    def _visible_query(self, actor: Actor) -> Select[tuple[ActionProjection]]:
        direct = and_(
            ActionProjection.recipient_user_id == actor.id,
            direct_request_access(actor),
        )
        candidate = and_(
            ActionProjection.candidate_role == actor.role,
            candidate_access(actor),
        )
        return select(ActionProjection).where(
            ActionProjection.is_active.is_(True), or_(direct, candidate)
        )
def utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
