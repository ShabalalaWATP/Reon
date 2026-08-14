"""Idempotent notification event, recipient and preference persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import (
    NotificationEvent,
    NotificationEventGroup,
    NotificationPreference,
    NotificationRecipient,
    ProjectionCheckpoint,
)
from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound, StaleVersion
from istari_service.identity_context import (
    active_actor_condition,
    actor_identity_context,
)
from istari_service.models import User
from istari_service.notification_preference_policy import MANDATORY_GROUPS
from istari_service.operational_analytics_projection import (
    project_notification_response_fact,
)
from istari_service.repositories.notification_access import (
    access_condition as _access_condition,
)
from istari_service.repositories.notification_access import (
    state_filter as _state_filter,
)
from istari_service.repositories.projection_pagination import (
    decode_cursor,
    encode_cursor,
)
from istari_service.schemas.actions import (
    NotificationFilterState,
    NotificationPreferenceUpdate,
    NotificationStateAction,
    NotificationStateTarget,
)


class SqlAlchemyNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
    ) -> tuple[list[tuple[NotificationRecipient, NotificationEvent]], str | None]:
        await self._require_current_actor(actor)
        query = self._visible_query(actor)
        if states:
            query = query.where(_state_filter(states))
        if event_types:
            query = query.where(NotificationEvent.event_type.in_(event_types))
        if from_date is not None:
            query = query.where(NotificationEvent.occurred_at >= from_date)
        if to_date is not None:
            query = query.where(NotificationEvent.occurred_at <= to_date)
        if cursor is not None:
            occurred_at, item_id = decode_cursor(
                cursor, message="The notification filters are invalid."
            )
            query = query.where(
                or_(
                    NotificationEvent.occurred_at < occurred_at,
                    and_(
                        NotificationEvent.occurred_at == occurred_at,
                        NotificationRecipient.id < item_id,
                    ),
                )
            )
        rows = list(
            (
                await self.session.execute(
                    query.order_by(
                        NotificationEvent.occurred_at.desc(),
                        NotificationRecipient.id.desc(),
                    ).limit(limit + 1)
                )
            )
            .tuples()
            .all()
        )
        if len(rows) <= limit:
            return rows, None
        recipient, event = rows[limit - 1]
        return rows[:limit], encode_cursor(event.occurred_at, recipient.id)

    async def unread_count(self, actor: Actor) -> int:
        await self._require_current_actor(actor)
        query = self._visible_query(actor).where(
            NotificationRecipient.read_at.is_(None),
            NotificationRecipient.archived_at.is_(None),
        )
        return int(
            await self.session.scalar(
                query.with_only_columns(func.count(NotificationRecipient.id))
            )
            or 0
        )

    async def mutate_state(
        self,
        actor: Actor,
        action: NotificationStateAction,
        targets: list[NotificationStateTarget],
        *,
        changed_at: datetime,
    ) -> list[tuple[NotificationRecipient, NotificationEvent]]:
        await self._require_current_actor(actor)
        rows = (
            await self.session.execute(
                self._visible_query(actor)
                .where(NotificationRecipient.id.in_({target.id for target in targets}))
                .with_for_update()
            )
        ).all()
        by_id = {recipient.id: (recipient, event) for recipient, event in rows}
        if len(by_id) != len(targets):
            raise ObjectNotFound()
        found = [by_id[target.id] for target in targets]
        for target, (recipient, _event) in zip(targets, found, strict=True):
            if recipient.version != target.expected_version:
                raise StaleVersion()
        for recipient, _event in found:
            if _apply_state(recipient, action, changed_at):
                recipient.version += 1
        for recipient, event in found:
            response_at = recipient.read_at or recipient.action_completed_at
            if response_at is not None:
                await project_notification_response_fact(
                    self.session,
                    event,
                    response_at,
                    unit_id=recipient.organisation_unit_id,
                )
        await self.session.flush()
        return found

    async def preferences(self, actor: Actor) -> list[NotificationPreference]:
        await self._require_current_actor(actor)
        context = actor_identity_context(actor)
        return list(
            (
                await self.session.scalars(
                    select(NotificationPreference)
                    .where(
                        NotificationPreference.user_id == actor.id,
                        NotificationPreference.identity_context == context,
                    )
                    .order_by(NotificationPreference.event_group)
                )
            ).all()
        )

    async def update_preference(
        self,
        actor: Actor,
        event_group: NotificationEventGroup,
        command: NotificationPreferenceUpdate,
    ) -> NotificationPreference:
        await self._require_current_actor(actor)
        context = actor_identity_context(actor)
        preference = await self.session.scalar(
            select(NotificationPreference)
            .where(
                NotificationPreference.user_id == actor.id,
                NotificationPreference.identity_context == context,
                NotificationPreference.event_group == event_group,
            )
            .with_for_update()
        )
        if preference is None:
            if command.expected_version != 0:
                raise StaleVersion()
            preference = NotificationPreference(
                user_id=actor.id,
                event_group=event_group,
                identity_context=context,
                enabled=command.enabled,
                reminder_days=command.reminder_days,
                version=1,
            )
            self.session.add(preference)
        else:
            if preference.version != command.expected_version:
                raise StaleVersion()
            preference.enabled = command.enabled
            preference.reminder_days = command.reminder_days
            preference.version += 1
        if event_group in MANDATORY_GROUPS:
            preference.enabled = True
        await self.session.flush()
        return preference

    async def checkpoint(self) -> ProjectionCheckpoint | None:
        return await self.session.get(ProjectionCheckpoint, "notifications")

    def _visible_query(
        self, actor: Actor
    ) -> Select[tuple[NotificationRecipient, NotificationEvent]]:
        return (
            select(NotificationRecipient, NotificationEvent)
            .join(
                NotificationEvent,
                NotificationEvent.id == NotificationRecipient.notification_event_id,
            )
            .where(
                NotificationRecipient.recipient_user_id == actor.id,
                NotificationRecipient.required_role == actor.role,
                _access_condition(actor),
            )
        )

    async def _require_current_actor(self, actor: Actor) -> None:
        current = await self.session.scalar(
            select(User.id).where(
                active_actor_condition(actor),
            )
        )
        if current is None:
            raise ObjectNotFound()


def _apply_state(
    recipient: NotificationRecipient,
    action: NotificationStateAction,
    changed_at: datetime,
) -> bool:
    before = (recipient.read_at, recipient.archived_at, recipient.action_completed_at)
    if action is NotificationStateAction.MARK_READ:
        recipient.read_at = recipient.read_at or changed_at
    elif action is NotificationStateAction.MARK_UNREAD:
        recipient.read_at = None
    elif action is NotificationStateAction.ARCHIVE:
        recipient.read_at = recipient.read_at or changed_at
        recipient.archived_at = recipient.archived_at or changed_at
    elif action is NotificationStateAction.RESTORE:
        recipient.archived_at = None
    else:
        recipient.read_at = recipient.read_at or changed_at
        recipient.action_completed_at = recipient.action_completed_at or changed_at
    return before != (
        recipient.read_at,
        recipient.archived_at,
        recipient.action_completed_at,
    )
