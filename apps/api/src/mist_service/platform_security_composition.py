"""Composition boundary for transactional platform-security use cases."""

from __future__ import annotations

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.platform_security_ports import (
    AssistanceBudgetPort,
    AssistanceDirectoryPort,
    AssistanceQueuePort,
    ClassificationPort,
    PasswordAssistancePublisherPort,
)
from mist_service.repositories.password_assistance_publisher import (
    SqlAlchemyPasswordAssistancePublisher,
)
from mist_service.repositories.platform_security_application import (
    SqlAlchemyPlatformSecurityApplication,
)
from mist_service.services.platform_security_service import PlatformSecurityService


def platform_security_service(
    session: AsyncSession,
    *,
    pseudonym_key: bytes = b"\0" * 32,
    pseudonym_key_id: str = "legacy",
) -> PlatformSecurityService:
    application = SqlAlchemyPlatformSecurityApplication(session)
    return PlatformSecurityService(
        cast(ClassificationPort, application),
        cast(AssistanceBudgetPort, application),
        cast(AssistanceDirectoryPort, application),
        cast(AssistanceQueuePort, application),
        cast(
            PasswordAssistancePublisherPort,
            SqlAlchemyPasswordAssistancePublisher(session),
        ),
        pseudonym_key=pseudonym_key,
        pseudonym_key_id=pseudonym_key_id,
    )
