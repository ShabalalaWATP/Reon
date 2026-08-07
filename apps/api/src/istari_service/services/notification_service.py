"""Application service for content-minimised, durable notifications."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from istari_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
    NotificationEventGroup,
    NotificationPreference,
    NotificationRecipient,
)
from istari_service.domain import Actor
from istari_service.errors import InvalidAction
from istari_service.notification_catalog import EVENT_LABELS, render_subject
from istari_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from istari_service.repositories.notifications import (
    MANDATORY_GROUPS,
    SqlAlchemyNotificationRepository,
)
from istari_service.repositories.projection_pagination import InvalidProjectionQuery
from istari_service.schemas.actions import (
    NotificationCountResult,
    NotificationFilterState,
    NotificationItem,
    NotificationListResult,
    NotificationPreferenceResult,
    NotificationPreferencesResult,
    NotificationPreferenceUpdate,
    NotificationStateCommand,
    NotificationStateResult,
)
from istari_service.services.action_service import _freshness


@dataclass(frozen=True, slots=True)
class NotificationEventCommand:
    stable_key: str
    event_type: str
    event_group: NotificationEventGroup
    source_version: int
    reference: str
    occurred_at: datetime
    request_id: UUID | None = None
    deep_link: str | None = None


class NotificationService:
    def __init__(
        self,
        repository: SqlAlchemyNotificationRepository,
        projection: SqlAlchemyNotificationProjectionRepository | None = None,
    ) -> None:
        self._repository = repository
        self._projection = projection

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
        now: datetime | None = None,
    ) -> NotificationListResult:
        await self._reconcile_pending()
        _validate_dates(from_date, to_date)
        normalised_types = _event_types(event_types)
        rows, next_cursor = await self._repository.list_notifications(
            actor,
            states=states,
            event_types=normalised_types,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            cursor=cursor,
        )
        checkpoint = await self._repository.checkpoint()
        current = now or datetime.now(UTC)
        return NotificationListResult(
            items=[_notification_item(recipient, event) for recipient, event in rows],
            unread_count=await self._repository.unread_count(actor),
            next_cursor=next_cursor,
            freshness=_freshness(checkpoint, current),
        )

    async def count(self, actor: Actor) -> NotificationCountResult:
        await self._reconcile_pending()
        checkpoint = await self._repository.checkpoint()
        return NotificationCountResult(
            unread_count=await self._repository.unread_count(actor),
            projected_at=checkpoint.projected_at if checkpoint else None,
        )

    async def mutate_state(
        self,
        actor: Actor,
        command: NotificationStateCommand,
        *,
        changed_at: datetime | None = None,
    ) -> NotificationStateResult:
        rows = await self._repository.mutate_state(
            actor,
            command.action,
            command.targets,
            changed_at=changed_at or datetime.now(UTC),
        )
        return NotificationStateResult(
            items=[_notification_item(recipient, event) for recipient, event in rows]
        )

    async def preferences(self, actor: Actor) -> NotificationPreferencesResult:
        stored = {
            preference.event_group: preference
            for preference in await self._repository.preferences(actor.id)
        }
        return NotificationPreferencesResult(
            groups=[
                _preference(group, stored.get(group))
                for group in NotificationEventGroup
            ]
        )

    async def update_preference(
        self,
        actor: Actor,
        event_group: NotificationEventGroup,
        command: NotificationPreferenceUpdate,
    ) -> NotificationPreferenceResult:
        preference = await self._repository.update_preference(
            actor.id, event_group, command
        )
        return _preference(event_group, preference)

    async def publish(self, command: NotificationEventCommand) -> NotificationEvent:
        projection = self._require_projection()
        event_type, subject = render_subject(command.event_type, command.reference)
        if command.source_version < 1 or not command.stable_key.strip():
            raise InvalidAction("The notification event source is invalid.")
        _validate_link(command.deep_link)
        return await projection.publish_event(
            stable_key=command.stable_key,
            event_type=event_type,
            event_group=command.event_group,
            source_version=command.source_version,
            request_id=command.request_id,
            safe_subject=subject,
            deep_link=command.deep_link,
            audience=[],
            occurred_at=command.occurred_at,
        )

    async def project(
        self,
        event_id: UUID,
        recipients: list[RecipientRule],
        *,
        projected_at: datetime | None = None,
    ) -> list[NotificationRecipient]:
        for rule in recipients:
            _validate_recipient_rule(rule)
        return await self._require_projection().project_event(
            event_id,
            recipients,
            projected_at=projected_at or datetime.now(UTC),
        )

    async def projection_failed(
        self,
        event_id: UUID,
        error_code: str,
        *,
        attempted_at: datetime | None = None,
    ) -> None:
        safe_code = error_code.strip().upper()
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,119}", safe_code) is None:
            safe_code = "PROJECTION_FAILED"
        await self._require_projection().mark_projection_failed(
            event_id,
            error_code=safe_code,
            attempted_at=attempted_at or datetime.now(UTC),
        )

    def _require_projection(self) -> SqlAlchemyNotificationProjectionRepository:
        if self._projection is None:
            raise RuntimeError("notification projection repository is not configured")
        return self._projection

    async def _reconcile_pending(self) -> None:
        if self._projection is None:
            return
        from istari_service.request_notification_projection import (
            reconcile_pending_notifications,
        )

        await reconcile_pending_notifications(self._projection.session)


def _notification_item(
    recipient: NotificationRecipient, event: NotificationEvent
) -> NotificationItem:
    return NotificationItem(
        id=recipient.id,
        event_type=event.event_type,
        event_group=event.event_group,
        subject=event.safe_subject,
        occurred_at=event.occurred_at,
        deep_link=event.deep_link,
        is_read=recipient.read_at is not None,
        is_archived=recipient.archived_at is not None,
        is_action_completed=recipient.action_completed_at is not None,
        read_at=recipient.read_at,
        archived_at=recipient.archived_at,
        action_completed_at=recipient.action_completed_at,
        version=recipient.version,
    )


def _preference(
    group: NotificationEventGroup, preference: NotificationPreference | None
) -> NotificationPreferenceResult:
    mandatory = group in MANDATORY_GROUPS
    return NotificationPreferenceResult(
        event_group=group,
        enabled=True if mandatory else preference.enabled if preference else True,
        mandatory=mandatory,
        reminder_days=list(preference.reminder_days) if preference else [],
        version=preference.version if preference else 0,
    )


def _validate_dates(from_date: datetime | None, to_date: datetime | None) -> None:
    if from_date is not None and from_date.tzinfo is None:
        raise InvalidProjectionQuery("Notification dates must include a time zone.")
    if to_date is not None and to_date.tzinfo is None:
        raise InvalidProjectionQuery("Notification dates must include a time zone.")
    if from_date is not None and to_date is not None and to_date < from_date:
        raise InvalidProjectionQuery("The notification date range is invalid.")


def _event_types(values: list[str]) -> list[str]:
    cleaned = [value.strip().upper() for value in values]
    if any(value not in EVENT_LABELS for value in cleaned):
        raise InvalidProjectionQuery("A notification event type is invalid.")
    return list(dict.fromkeys(cleaned))


def _validate_link(link: str | None) -> None:
    if link is None:
        return
    if (
        not link.startswith("/")
        or link.startswith("//")
        or "\\" in link
        or any(char in link for char in "\r\n")
    ):
        raise InvalidAction("A notification link must be application-local.")


def _validate_recipient_rule(rule: RecipientRule) -> None:
    if rule.access_kind is NotificationAccessKind.ACCOUNT:
        if rule.organisation_unit_id is not None:
            raise InvalidAction("An account notification rule is invalid.")
    elif rule.access_kind is NotificationAccessKind.REQUESTER:
        if rule.required_role.value != "REQUESTER":
            raise InvalidAction("A Customer notification rule is invalid.")
    elif rule.access_kind is NotificationAccessKind.ROUTE_MEMBER:
        if rule.organisation_unit_id is None:
            raise InvalidAction("A routed notification requires an organisation unit.")
    elif (
        rule.access_kind is NotificationAccessKind.ROLE_SCOPE
        and not rule.required_scope
    ):
        raise InvalidAction("A scoped notification requires a scope.")
