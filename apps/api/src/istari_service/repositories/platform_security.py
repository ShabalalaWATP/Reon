"""Persistence for the global marking and access-assistance controls."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select
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
        self, *, source_key: str, matched_user_id: UUID | None
    ) -> PasswordAssistanceAttempt:
        attempt = PasswordAssistanceAttempt(
            source_key=source_key,
            matched_user_id=matched_user_id,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

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
