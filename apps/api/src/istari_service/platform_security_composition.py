"""Composition boundary for transactional platform-security use cases."""

from __future__ import annotations

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.platform_security_ports import (
    PasswordAssistancePublisherPort,
    PlatformSecurityApplicationPort,
)
from istari_service.repositories.password_assistance_publisher import (
    SqlAlchemyPasswordAssistancePublisher,
)
from istari_service.repositories.platform_security_application import (
    SqlAlchemyPlatformSecurityApplication,
)
from istari_service.services.platform_security_service import PlatformSecurityService


def platform_security_service(
    session: AsyncSession,
    *,
    pseudonym_key: bytes = b"\0" * 32,
    pseudonym_key_id: str = "legacy",
) -> PlatformSecurityService:
    return PlatformSecurityService(
        cast(
            PlatformSecurityApplicationPort,
            SqlAlchemyPlatformSecurityApplication(session),
        ),
        cast(
            PasswordAssistancePublisherPort,
            SqlAlchemyPasswordAssistancePublisher(session),
        ),
        pseudonym_key=pseudonym_key,
        pseudonym_key_id=pseudonym_key_id,
    )
