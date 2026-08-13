"""Persistence for the global marking and access-assistance controls."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.models import User, UserRole
from istari_service.platform_security_models import (
    PLATFORM_CLASSIFICATION_ID,
    PasswordAssistanceAttempt,
    PlatformClassification,
    PlatformClassificationSetting,
)


class SqlAlchemyPlatformSecurityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def classification(
        self, *, lock: bool = False
    ) -> PlatformClassificationSetting:
        query = select(PlatformClassificationSetting).where(
            PlatformClassificationSetting.id == PLATFORM_CLASSIFICATION_ID
        )
        if lock:
            query = query.with_for_update()
        setting = await self.session.scalar(query)
        if setting is None:
            setting = PlatformClassificationSetting(
                id=PLATFORM_CLASSIFICATION_ID,
                classification=PlatformClassification.OFFICIAL,
                version=1,
            )
            self.session.add(setting)
            await self.session.flush()
        return setting

    async def active_user_by_email(self, email: str) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(
                select(User)
                .where(User.email == email, User.is_active.is_(True))
                .with_for_update()
            ),
        )

    async def lock_assistance_budget(self) -> None:
        """Serialise budget decisions so concurrent requests cannot oversubscribe."""

        await self.classification(lock=True)

    async def attempt_count(
        self, *, since: datetime, source_key: str | None = None
    ) -> int:
        query = select(func.count(PasswordAssistanceAttempt.id)).where(
            PasswordAssistanceAttempt.created_at >= since
        )
        if source_key is not None:
            query = query.where(PasswordAssistanceAttempt.source_key == source_key)
        return int(await self.session.scalar(query) or 0)

    async def has_recent_user_attempt(self, user_id: UUID, since: datetime) -> bool:
        return (
            await self.session.scalar(
                select(PasswordAssistanceAttempt.id)
                .where(
                    PasswordAssistanceAttempt.matched_user_id == user_id,
                    PasswordAssistanceAttempt.created_at >= since,
                )
                .limit(1)
            )
            is not None
        )

    async def add_attempt(
        self,
        *,
        source_key: str,
        matched_user_id: UUID | None,
        email_hash: str | None = None,
        email_key_id: str | None = None,
    ) -> PasswordAssistanceAttempt:
        attempt = PasswordAssistanceAttempt(
            source_key=source_key,
            matched_user_id=matched_user_id,
            email_hash=email_hash,
            email_key_id=email_key_id,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def pending_attempt(self, now: datetime) -> PasswordAssistanceAttempt | None:
        return cast(
            PasswordAssistanceAttempt | None,
            await self.session.scalar(
                select(PasswordAssistanceAttempt)
                .where(
                    PasswordAssistanceAttempt.processing_status == "PENDING",
                    (PasswordAssistanceAttempt.next_attempt_at.is_(None))
                    | (PasswordAssistanceAttempt.next_attempt_at <= now),
                )
                .order_by(PasswordAssistanceAttempt.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            ),
        )

    async def active_user_by_email_hash(
        self, email_hash: str, key_id: str
    ) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(
                select(User).where(
                    User.assistance_email_hash == email_hash,
                    User.assistance_email_key_id == key_id,
                    User.is_active.is_(True),
                )
            ),
        )

    async def users_needing_assistance_index(
        self, key_id: str, *, limit: int = 100
    ) -> list[User]:
        return list(
            await self.session.scalars(
                select(User)
                .where(
                    (User.assistance_email_hash.is_(None))
                    | (User.assistance_email_key_id != key_id)
                )
                .order_by(User.id)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        )

    async def assistance_index_is_complete(self, key_id: str) -> bool:
        return (
            await self.session.scalar(
                select(User.id)
                .where(
                    (User.assistance_email_hash.is_(None))
                    | (User.assistance_email_key_id != key_id)
                )
                .limit(1)
            )
            is None
        )

    def complete_attempt(
        self, attempt: PasswordAssistanceAttempt, now: datetime
    ) -> None:
        attempt.processing_status = "COMPLETED"
        attempt.processed_at = now

    def retry_attempt(self, attempt: PasswordAssistanceAttempt, now: datetime) -> None:
        attempt.processing_attempts += 1
        if attempt.processing_attempts >= 5:
            attempt.processing_status = "FAILED"
        else:
            attempt.next_attempt_at = now + timedelta(
                seconds=2**attempt.processing_attempts
            )

    async def match_attempt(self, attempt_id: UUID, user_id: UUID) -> None:
        await self.session.execute(
            update(PasswordAssistanceAttempt)
            .where(PasswordAssistanceAttempt.id == attempt_id)
            .values(matched_user_id=user_id)
        )

    async def active_administrators(self) -> list[User]:
        return list(
            await self.session.scalars(
                select(User).where(
                    User.role == UserRole.PLATFORM_ADMIN,
                    User.is_active.is_(True),
                )
            )
        )

    async def prune_attempts(self, before: datetime) -> None:
        await self.session.execute(
            delete(PasswordAssistanceAttempt)
            .where(PasswordAssistanceAttempt.created_at < before)
            .execution_options(synchronize_session=False)
        )


async def initialise_platform_classification(session: AsyncSession) -> None:
    """Ensure schema-created test databases receive the migration-owned default."""
    await SqlAlchemyPlatformSecurityRepository(session).classification()
