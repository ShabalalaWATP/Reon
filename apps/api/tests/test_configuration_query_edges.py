"""Fail-closed configuration query behaviour."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from istari_service.config import Environment, Settings
from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound
from istari_service.models import UserRole
from istari_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from istari_service.services.configuration_query_service import (
    ConfigurationQueryService,
)


async def test_active_configuration_fails_closed_when_registry_is_empty() -> None:
    repository = Mock()
    repository.active_bundle = AsyncMock(return_value=None)
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        configuration_admin_enabled=True,
    )
    actor = Actor(
        id=uuid4(),
        username="configuration.admin@example.test",
        display_name="Configuration Administrator",
        role=UserRole.PLATFORM_ADMIN,
        scope="Platform",
    )

    service = ConfigurationQueryService(
        cast(SqlAlchemyConfigurationRepository, repository), settings
    )
    with pytest.raises(ObjectNotFound):
        await service.active(actor)
