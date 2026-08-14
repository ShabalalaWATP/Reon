"""Notification adapter for content-minimised password assistance."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEventGroup,
)
from istari_service.models import UserRole
from istari_service.notification_catalog import render_subject
from istari_service.notification_ports import RecipientRule
from istari_service.notification_rule_serialisation import serialise_rule
from istari_service.platform_security_ports import AssistanceUserRecord
from istari_service.repositories.notification_projection import (
    SqlAlchemyNotificationProjectionRepository,
)


class SqlAlchemyPasswordAssistancePublisher:
    def __init__(self, session: AsyncSession) -> None:
        self._notifications = SqlAlchemyNotificationProjectionRepository(session)

    async def publish_password_assistance(
        self,
        attempt_id: UUID,
        user: AssistanceUserRecord,
        administrator_ids: list[UUID],
        occurred_at: datetime,
    ) -> None:
        event_type, subject = render_subject(
            "PASSWORD_ASSISTANCE_REQUESTED", user.username
        )
        rules = [
            RecipientRule(
                administrator_id,
                NotificationAccessKind.ACCOUNT,
                UserRole.PLATFORM_ADMIN,
            )
            for administrator_id in administrator_ids
        ]
        await self._notifications.publish_event(
            stable_key=f"password-assistance:{attempt_id}",
            event_type=event_type,
            event_group=NotificationEventGroup.ACCOUNT_SECURITY,
            source_version=1,
            request_id=None,
            safe_subject=subject,
            deep_link=f"/admin/users/{user.id}",
            audience=[serialise_rule(rule) for rule in rules],
            occurred_at=occurred_at,
        )
