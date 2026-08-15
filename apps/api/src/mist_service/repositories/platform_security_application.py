"""SQLAlchemy adapter for platform-security application contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.admin_audit import append_admin_event
from mist_service.models import User
from mist_service.platform_security_models import (
    PasswordAssistanceAttempt,
)
from mist_service.platform_security_ports import (
    AssistanceAttemptRecord,
    AssistanceUserRecord,
    ClassificationRecord,
)
from mist_service.platform_security_types import PlatformClassification
from mist_service.repositories.platform_security import (
    SqlAlchemyPlatformSecurityRepository,
)
from mist_service.schemas.platform_security import PlatformClassificationView


class SqlAlchemyPlatformSecurityApplication:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = SqlAlchemyPlatformSecurityRepository(session)

    async def classification(self, *, lock: bool = False) -> ClassificationRecord:
        setting = await self._repository.classification(lock=lock)
        return ClassificationRecord(
            setting.id,
            setting.classification,
            setting.version,
            setting.updated_at,
        )

    async def update_classification(
        self,
        setting: ClassificationRecord,
        *,
        classification: PlatformClassification,
        actor_id: UUID,
    ) -> PlatformClassificationView:
        stored = await self._repository.classification(lock=True)
        if stored.id != setting.id or stored.version != setting.version:
            from mist_service.errors import StaleVersion

            raise StaleVersion()
        stored.classification = classification
        stored.updated_by_user_id = actor_id
        stored.version += 1
        await append_admin_event(
            self._session,
            actor_id=actor_id,
            action="CLASSIFICATION_UPDATED",
            target_type="PLATFORM_SETTING",
            target_id=stored.id,
            changed_fields=["classification"],
            summary="Global classification marking updated.",
        )
        await self._session.flush()
        await self._session.refresh(stored)
        return PlatformClassificationView.model_validate(stored)

    async def active_user_by_email(self, email: str) -> AssistanceUserRecord | None:
        return _user(await self._repository.active_user_by_email(email))

    async def lock_assistance_budget(self) -> None:
        await self._repository.lock_assistance_budget()

    async def attempt_count(
        self, *, since: datetime, source_key: str | None = None
    ) -> int:
        return await self._repository.attempt_count(since=since, source_key=source_key)

    async def has_recent_user_attempt(self, user_id: UUID, since: datetime) -> bool:
        return await self._repository.has_recent_user_attempt(user_id, since)

    async def add_attempt(
        self,
        *,
        source_key: str,
        matched_user_id: UUID | None,
        email_hash: str | None = None,
        email_key_id: str | None = None,
    ) -> UUID:
        attempt = await self._repository.add_attempt(
            source_key=source_key,
            matched_user_id=matched_user_id,
            email_hash=email_hash,
            email_key_id=email_key_id,
        )
        return attempt.id

    async def pending_attempt(self, now: datetime) -> AssistanceAttemptRecord | None:
        attempt = await self._repository.pending_attempt(now)
        return _attempt(attempt)

    async def active_user_by_email_hash(
        self, email_hash: str, key_id: str
    ) -> AssistanceUserRecord | None:
        return _user(
            await self._repository.active_user_by_email_hash(email_hash, key_id)
        )

    async def users_needing_assistance_index(
        self, key_id: str
    ) -> list[AssistanceUserRecord]:
        users = await self._repository.users_needing_assistance_index(key_id)
        return [_required_user(user) for user in users]

    async def set_assistance_index(
        self, user_id: UUID, *, email_hash: str, key_id: str
    ) -> None:
        user = await self._session.get(User, user_id)
        if user is not None:
            user.assistance_email_hash = email_hash
            user.assistance_email_key_id = key_id

    async def assistance_index_is_complete(self, key_id: str) -> bool:
        return await self._repository.assistance_index_is_complete(key_id)

    async def complete_attempt(self, attempt_id: UUID, now: datetime) -> None:
        attempt = await self._session.get(PasswordAssistanceAttempt, attempt_id)
        if attempt is not None:
            self._repository.complete_attempt(attempt, now)

    async def retry_attempt(self, attempt_id: UUID, now: datetime) -> None:
        attempt = await self._session.get(PasswordAssistanceAttempt, attempt_id)
        if attempt is not None:
            self._repository.retry_attempt(attempt, now)

    async def match_attempt(self, attempt_id: UUID, user_id: UUID) -> None:
        await self._repository.match_attempt(attempt_id, user_id)

    async def active_administrator_ids(self) -> list[UUID]:
        return [user.id for user in await self._repository.active_administrators()]

    async def prune_attempts(self, before: datetime) -> None:
        await self._repository.prune_attempts(before)


def _user(user: User | None) -> AssistanceUserRecord | None:
    return _required_user(user) if user is not None else None


def _required_user(user: User) -> AssistanceUserRecord:
    return AssistanceUserRecord(user.id, user.username, user.email)


def _attempt(
    attempt: PasswordAssistanceAttempt | None,
) -> AssistanceAttemptRecord | None:
    if attempt is None:
        return None
    return AssistanceAttemptRecord(attempt.id, attempt.email_hash, attempt.email_key_id)
