"""Global classification and non-enumerating password-assistance use cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from istari_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEventGroup,
)
from istari_service.admin_audit import append_admin_event
from istari_service.domain import Actor
from istari_service.errors import (
    AdministrationAccessDenied,
    StaleVersion,
)
from istari_service.models import User, UserRole
from istari_service.notification_catalog import render_subject
from istari_service.notification_rule_serialisation import serialise_rule
from istari_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from istari_service.repositories.platform_security import (
    SqlAlchemyPlatformSecurityRepository,
)
from istari_service.schemas.platform_security import (
    PlatformClassificationUpdate,
    PlatformClassificationView,
)

ASSISTANCE_WINDOW = timedelta(minutes=15)
ASSISTANCE_RETENTION = timedelta(days=7)
SOURCE_ATTEMPT_LIMIT = 5
GLOBAL_ATTEMPT_LIMIT = 500


class PlatformSecurityService:
    def __init__(self, repository: SqlAlchemyPlatformSecurityRepository) -> None:
        self._repository = repository

    async def classification(self) -> PlatformClassificationView:
        return PlatformClassificationView.model_validate(
            await self._repository.classification()
        )

    async def update_classification(
        self,
        actor: Actor,
        command: PlatformClassificationUpdate,
    ) -> PlatformClassificationView:
        if actor.role is not UserRole.PLATFORM_ADMIN:
            raise AdministrationAccessDenied()
        setting = await self._repository.classification(lock=True)
        if setting.version != command.expected_version:
            raise StaleVersion()
        if setting.classification is command.classification:
            return PlatformClassificationView.model_validate(setting)
        setting.classification = command.classification
        setting.updated_by_user_id = actor.id
        setting.version += 1
        await append_admin_event(
            self._repository.session,
            actor_id=actor.id,
            action="CLASSIFICATION_UPDATED",
            target_type="PLATFORM_SETTING",
            target_id=setting.id,
            changed_fields=["classification"],
            summary="Global classification marking updated.",
        )
        await self._repository.session.flush()
        await self._repository.session.refresh(setting)
        return PlatformClassificationView.model_validate(setting)

    async def request_password_assistance(
        self,
        email: str,
        *,
        source_key: str,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        since = current - ASSISTANCE_WINDOW
        source_count = await self._repository.attempt_count(
            since=since,
            source_key=source_key,
        )
        global_count = await self._repository.attempt_count(since=since)
        if source_count >= SOURCE_ATTEMPT_LIMIT or global_count >= GLOBAL_ATTEMPT_LIMIT:
            return

        user = await self._repository.active_user_by_email(email)
        recent = bool(
            user and await self._repository.has_recent_user_attempt(user.id, since)
        )
        attempt = await self._repository.add_attempt(
            source_key=source_key,
            matched_user_id=user.id if user else None,
        )
        if user is not None and not recent:
            await self._publish_password_assistance(attempt.id, user, current)
        await self._repository.prune_attempts(current - ASSISTANCE_RETENTION)

    async def _publish_password_assistance(
        self, attempt_id: UUID, user: User, occurred_at: datetime
    ) -> None:
        event_type, subject = render_subject(
            "PASSWORD_ASSISTANCE_REQUESTED",
            user.username,
        )
        administrators = await self._repository.active_administrators()
        rules = [
            RecipientRule(
                administrator.id,
                NotificationAccessKind.ACCOUNT,
                UserRole.PLATFORM_ADMIN,
            )
            for administrator in administrators
        ]
        await SqlAlchemyNotificationProjectionRepository(
            self._repository.session
        ).publish_event(
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
