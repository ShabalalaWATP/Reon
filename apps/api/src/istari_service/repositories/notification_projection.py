"""Transactional notification event publication and recipient projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEvent,
    NotificationEventGroup,
    NotificationPreference,
    NotificationProjectionStatus,
    NotificationRecipient,
    ProjectionCheckpoint,
    ProjectionHealth,
)
from istari_service.errors import ObjectNotFound
from istari_service.models import User, UserRole
from istari_service.operational_analytics_projection import (
    project_notification_sent_fact,
)
from istari_service.organisation_models import UserOrganisationMembership
from istari_service.repositories.notifications import MANDATORY_GROUPS


@dataclass(frozen=True, slots=True)
class RecipientRule:
    user_id: UUID
    access_kind: NotificationAccessKind
    required_role: UserRole
    required_scope: str | None = None
    organisation_unit_id: UUID | None = None


class SqlAlchemyNotificationProjectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
    ) -> NotificationEvent:
        existing = await self.session.scalar(
            select(NotificationEvent).where(NotificationEvent.stable_key == stable_key)
        )
        if existing is not None:
            return existing
        event = NotificationEvent(
            stable_key=stable_key,
            event_type=event_type.strip().upper(),
            event_group=event_group,
            source_version=source_version,
            request_id=request_id,
            safe_subject=safe_subject.strip(),
            deep_link=deep_link,
            audience=audience,
            occurred_at=occurred_at,
            status=NotificationProjectionStatus.PENDING,
            attempts=0,
            available_at=occurred_at,
        )
        self.session.add(event)
        await self.session.flush()
        await project_notification_sent_fact(self.session, event)
        return event

    async def pending_events(
        self, *, limit: int, available_at: datetime
    ) -> list[NotificationEvent]:
        return list(
            (
                await self.session.scalars(
                    select(NotificationEvent)
                    .where(
                        NotificationEvent.status.in_(
                            [
                                NotificationProjectionStatus.PENDING,
                                NotificationProjectionStatus.FAILED,
                            ]
                        ),
                        NotificationEvent.available_at <= available_at,
                    )
                    .order_by(NotificationEvent.available_at, NotificationEvent.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )

    async def project_event(
        self,
        event_id: UUID,
        recipients: list[RecipientRule],
        *,
        projected_at: datetime,
    ) -> list[NotificationRecipient]:
        event = await self.session.scalar(
            select(NotificationEvent)
            .where(NotificationEvent.id == event_id)
            .with_for_update()
        )
        if event is None:
            raise ObjectNotFound()
        if event.status is NotificationProjectionStatus.PROJECTED:
            return await self._event_recipients(event.id)
        event.attempts += 1
        created: list[NotificationRecipient] = []
        seen: set[UUID] = set()
        for rule in recipients:
            if rule.user_id in seen or not await self._recipient_is_current(rule):
                continue
            seen.add(rule.user_id)
            if not await self._enabled(rule.user_id, event.event_group):
                continue
            recipient = await self._find_recipient(event.id, rule.user_id)
            if recipient is None:
                recipient = NotificationRecipient(
                    notification_event_id=event.id,
                    recipient_user_id=rule.user_id,
                    idempotency_key=f"{event.stable_key}:{rule.user_id}",
                    access_kind=rule.access_kind,
                    required_role=rule.required_role,
                    required_scope=rule.required_scope,
                    organisation_unit_id=rule.organisation_unit_id,
                    version=1,
                )
                self.session.add(recipient)
                await self.session.flush()
            created.append(recipient)
        event.status = NotificationProjectionStatus.PROJECTED
        event.projected_at = projected_at
        event.last_error = None
        unit_id = next(
            (
                item.organisation_unit_id
                for item in created
                if item.organisation_unit_id
            ),
            None,
        )
        await project_notification_sent_fact(self.session, event, unit_id=unit_id)
        await self._set_checkpoint(event, projected_at, failed=False)
        return created

    async def mark_projection_failed(
        self, event_id: UUID, *, error_code: str, attempted_at: datetime
    ) -> None:
        event = await self.session.scalar(
            select(NotificationEvent)
            .where(NotificationEvent.id == event_id)
            .with_for_update()
        )
        if event is None:
            raise ObjectNotFound()
        event.attempts += 1
        event.status = NotificationProjectionStatus.FAILED
        event.last_error = error_code[:120]
        event.available_at = attempted_at
        await self._set_checkpoint(event, attempted_at, failed=True)

    async def _event_recipients(self, event_id: UUID) -> list[NotificationRecipient]:
        return list(
            (
                await self.session.scalars(
                    select(NotificationRecipient).where(
                        NotificationRecipient.notification_event_id == event_id
                    )
                )
            ).all()
        )

    async def _recipient_is_current(self, rule: RecipientRule) -> bool:
        query = select(User.id).where(
            User.id == rule.user_id,
            User.is_active.is_(True),
            User.role == rule.required_role,
        )
        if rule.organisation_unit_id is not None:
            query = query.join(
                UserOrganisationMembership,
                UserOrganisationMembership.user_id == User.id,
            ).where(UserOrganisationMembership.unit_id == rule.organisation_unit_id)
        elif rule.required_scope is not None:
            query = query.where(User.scope == rule.required_scope)
        return await self.session.scalar(query) is not None

    async def _enabled(self, user_id: UUID, group: NotificationEventGroup) -> bool:
        if group in MANDATORY_GROUPS:
            return True
        enabled = await self.session.scalar(
            select(NotificationPreference.enabled).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.event_group == group,
            )
        )
        return enabled is not False

    async def _find_recipient(
        self, event_id: UUID, user_id: UUID
    ) -> NotificationRecipient | None:
        return cast(
            NotificationRecipient | None,
            await self.session.scalar(
                select(NotificationRecipient).where(
                    NotificationRecipient.notification_event_id == event_id,
                    NotificationRecipient.recipient_user_id == user_id,
                )
            ),
        )

    async def _set_checkpoint(
        self, event: NotificationEvent, projected_at: datetime, *, failed: bool
    ) -> None:
        checkpoint = await self.session.get(ProjectionCheckpoint, "notifications")
        if checkpoint is None:
            checkpoint = ProjectionCheckpoint(name="notifications")
            self.session.add(checkpoint)
        checkpoint.last_event_key = event.stable_key
        checkpoint.source_changed_at = event.occurred_at
        checkpoint.projected_at = projected_at
        checkpoint.pending_count = await self._status_count(
            NotificationProjectionStatus.PENDING
        )
        checkpoint.failed_count = await self._status_count(
            NotificationProjectionStatus.FAILED
        )
        checkpoint.health = (
            ProjectionHealth.DEGRADED
            if failed or checkpoint.failed_count
            else ProjectionHealth.CURRENT
        )

    async def _status_count(self, status: NotificationProjectionStatus) -> int:
        return int(
            await self.session.scalar(
                select(func.count(NotificationEvent.id)).where(
                    NotificationEvent.status == status
                )
            )
            or 0
        )
