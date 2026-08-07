"""Idempotent notification event, recipient and preference persistence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
    NotificationEventGroup,
    NotificationPreference,
    NotificationRecipient,
    ProjectionCheckpoint,
)
from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound, StaleVersion
from istari_service.models import ServiceRequest, User, WorkflowTask
from istari_service.operational_analytics_projection import (
    project_notification_response_fact,
)
from istari_service.organisation_models import (
    RequestRouteSelection,
    UserOrganisationMembership,
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

MANDATORY_GROUPS = frozenset(
    {NotificationEventGroup.RELEASE, NotificationEventGroup.ACCOUNT_SECURITY}
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
        found: list[tuple[NotificationRecipient, NotificationEvent]] = []
        for target in targets:
            row = await self.session.execute(
                self._visible_query(actor)
                .where(NotificationRecipient.id == target.id)
                .with_for_update()
            )
            item = row.one_or_none()
            if item is None:
                raise ObjectNotFound()
            recipient, event = item
            if recipient.version != target.expected_version:
                raise StaleVersion()
            found.append((recipient, event))
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

    async def preferences(self, user_id: UUID) -> list[NotificationPreference]:
        return list(
            (
                await self.session.scalars(
                    select(NotificationPreference)
                    .where(NotificationPreference.user_id == user_id)
                    .order_by(NotificationPreference.event_group)
                )
            ).all()
        )

    async def update_preference(
        self,
        user_id: UUID,
        event_group: NotificationEventGroup,
        command: NotificationPreferenceUpdate,
    ) -> NotificationPreference:
        preference = await self.session.scalar(
            select(NotificationPreference)
            .where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.event_group == event_group,
            )
            .with_for_update()
        )
        if preference is None:
            if command.expected_version != 0:
                raise StaleVersion()
            preference = NotificationPreference(
                user_id=user_id,
                event_group=event_group,
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
                User.id == actor.id,
                User.is_active.is_(True),
                User.role == actor.role,
                User.scope == actor.scope,
            )
        )
        if current is None:
            raise ObjectNotFound()


def _access_condition(actor: Actor) -> ColumnElement[bool]:
    account = and_(
        NotificationRecipient.access_kind == NotificationAccessKind.ACCOUNT,
        NotificationEvent.request_id.is_(None),
    )
    requester = and_(
        NotificationRecipient.access_kind == NotificationAccessKind.REQUESTER,
        exists().where(
            ServiceRequest.id == NotificationEvent.request_id,
            ServiceRequest.requester_id == actor.id,
        ),
    )
    assignee = and_(
        NotificationRecipient.access_kind == NotificationAccessKind.ASSIGNEE,
        or_(
            exists().where(
                ServiceRequest.id == NotificationEvent.request_id,
                ServiceRequest.assigned_specialist_id == actor.id,
            ),
            exists().where(
                WorkflowTask.request_id == NotificationEvent.request_id,
                WorkflowTask.assignee_user_id == actor.id,
                WorkflowTask.candidate_role == actor.role,
                WorkflowTask.completed_at.is_(None),
            ),
        ),
    )
    route_member = and_(
        NotificationRecipient.access_kind == NotificationAccessKind.ROUTE_MEMBER,
        exists().where(
            UserOrganisationMembership.user_id == actor.id,
            UserOrganisationMembership.unit_id
            == NotificationRecipient.organisation_unit_id,
        ),
        or_(
            NotificationEvent.request_id.is_(None),
            exists().where(
                RequestRouteSelection.request_id == NotificationEvent.request_id,
                RequestRouteSelection.unit_id
                == NotificationRecipient.organisation_unit_id,
            ),
        ),
    )
    role_scope = and_(
        NotificationRecipient.access_kind == NotificationAccessKind.ROLE_SCOPE,
        NotificationRecipient.required_scope == actor.scope,
        or_(
            NotificationEvent.request_id.is_(None),
            exists().where(
                WorkflowTask.request_id == NotificationEvent.request_id,
                WorkflowTask.candidate_role == actor.role,
                WorkflowTask.completed_at.is_(None),
            ),
        ),
    )
    return or_(account, requester, assignee, route_member, role_scope)


def _state_filter(states: list[NotificationFilterState]) -> ColumnElement[bool]:
    conditions: list[ColumnElement[bool]] = []
    if NotificationFilterState.UNREAD in states:
        conditions.append(
            and_(
                NotificationRecipient.read_at.is_(None),
                NotificationRecipient.archived_at.is_(None),
            )
        )
    if NotificationFilterState.READ in states:
        conditions.append(
            and_(
                NotificationRecipient.read_at.is_not(None),
                NotificationRecipient.archived_at.is_(None),
            )
        )
    if NotificationFilterState.ARCHIVED in states:
        conditions.append(NotificationRecipient.archived_at.is_not(None))
    if NotificationFilterState.ACTION_COMPLETED in states:
        conditions.append(NotificationRecipient.action_completed_at.is_not(None))
    return or_(*conditions)


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
