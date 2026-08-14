"""Global classification and non-enumerating password-assistance use cases."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID

from istari_service.domain import Actor
from istari_service.errors import (
    AdministrationAccessDenied,
    StaleVersion,
)
from istari_service.models import UserRole
from istari_service.platform_security_ports import (
    AssistanceUserRecord,
    PasswordAssistancePublisherPort,
    PlatformSecurityApplicationPort,
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
    def __init__(
        self,
        repository: PlatformSecurityApplicationPort,
        publisher: PasswordAssistancePublisherPort,
        *,
        pseudonym_key: bytes = b"\0" * 32,
        pseudonym_key_id: str = "legacy",
    ) -> None:
        if len(pseudonym_key) < 32:
            raise ValueError("security pseudonym key must be at least 32 bytes")
        self._repository = repository
        self._publisher = publisher
        self._pseudonym_key = pseudonym_key
        self._pseudonym_key_id = pseudonym_key_id

    async def classification(self) -> PlatformClassificationView:
        setting = await self._repository.classification()
        return PlatformClassificationView(
            classification=setting.classification,
            version=setting.version,
            updatedAt=setting.updated_at,
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
            return PlatformClassificationView(
                classification=setting.classification,
                version=setting.version,
                updatedAt=setting.updated_at,
            )
        return await self._repository.update_classification(
            setting,
            classification=command.classification,
            actor_id=actor.id,
        )

    async def request_password_assistance(
        self,
        email: str,
        *,
        source_key: str,
        now: datetime | None = None,
    ) -> UUID | None:
        current = now or datetime.now(UTC)
        since = current - ASSISTANCE_WINDOW
        await self._repository.lock_assistance_budget()
        source_count = await self._repository.attempt_count(
            since=since,
            source_key=source_key,
        )
        global_count = await self._repository.attempt_count(since=since)
        allowed = (
            source_count < SOURCE_ATTEMPT_LIMIT and global_count < GLOBAL_ATTEMPT_LIMIT
        )
        if not allowed:
            return None
        attempt_id = await self._repository.add_attempt(
            source_key=source_key,
            matched_user_id=None,
            email_hash=self._email_hash(email),
            email_key_id=self._pseudonym_key_id,
        )
        await self._repository.prune_attempts(current - ASSISTANCE_RETENTION)
        return attempt_id

    def _email_hash(self, email: str) -> str:
        return hmac.new(
            self._pseudonym_key,
            f"istari-password-assistance-email-v1:{email.strip().casefold()}".encode(),
            hashlib.sha256,
        ).hexdigest()

    async def reconcile_assistance_email_indexes(self) -> bool:
        users = await self._repository.users_needing_assistance_index(
            self._pseudonym_key_id
        )
        for user in users:
            await self._repository.set_assistance_index(
                user.id,
                email_hash=self._email_hash(user.email),
                key_id=self._pseudonym_key_id,
            )
        return bool(users)

    async def process_password_assistance(
        self, attempt_id: UUID, email: str, *, now: datetime | None = None
    ) -> None:
        current = now or datetime.now(UTC)
        since = current - ASSISTANCE_WINDOW
        user = await self._repository.active_user_by_email(email)
        recent = bool(
            user and await self._repository.has_recent_user_attempt(user.id, since)
        )
        if user is not None:
            await self._repository.match_attempt(attempt_id, user.id)
        if user is not None and not recent:
            await self._publish_password_assistance(attempt_id, user, current)

    async def process_pending_password_assistance(self) -> bool:
        reconciled = await self.reconcile_assistance_email_indexes()
        if not await self._repository.assistance_index_is_complete(
            self._pseudonym_key_id
        ):
            return True
        now = datetime.now(UTC)
        attempt = await self._repository.pending_attempt(now)
        if attempt is None:
            return reconciled
        if attempt.email_key_id != self._pseudonym_key_id:
            await self._repository.retry_attempt(attempt.id, now)
            return True
        try:
            user = await self._repository.active_user_by_email_hash(
                attempt.email_hash or "", attempt.email_key_id or ""
            )
            since = now - ASSISTANCE_WINDOW
            recent = bool(
                user and await self._repository.has_recent_user_attempt(user.id, since)
            )
            if user is not None:
                await self._repository.match_attempt(attempt.id, user.id)
            if user is not None and not recent:
                await self._publish_password_assistance(attempt.id, user, now)
            await self._repository.complete_attempt(attempt.id, now)
        except Exception:
            await self._repository.retry_attempt(attempt.id, now)
        return True

    async def _publish_password_assistance(
        self, attempt_id: UUID, user: AssistanceUserRecord, occurred_at: datetime
    ) -> None:
        await self._publisher.publish_password_assistance(
            attempt_id,
            user,
            await self._repository.active_administrator_ids(),
            occurred_at,
        )
