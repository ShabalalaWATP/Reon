"""FastAPI composition boundary for configuration administration use cases."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from mist_service.configuration_events import ConfigurationEventPublisher
from mist_service.dependencies import AppSettings, DatabaseSession
from mist_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from mist_service.services.configuration_lifecycle_service import (
    ConfigurationLifecycleService,
)
from mist_service.services.configuration_ports import (
    ConfigurationApplicationPort,
    ConfigurationQueryPort,
)
from mist_service.services.configuration_query_service import (
    ConfigurationQueryService,
)


def configuration_query_service(
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationQueryService:
    """Compose the read use case from one request-scoped SQLAlchemy adapter."""

    return ConfigurationQueryService(
        cast(ConfigurationQueryPort, SqlAlchemyConfigurationRepository(session)),
        settings,
    )


def configuration_lifecycle_service(
    request: Request,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationLifecycleService:
    """Compose command use cases inside the request transaction boundary."""

    publisher = cast(
        ConfigurationEventPublisher | None,
        getattr(request.app.state, "configuration_event_publisher", None),
    )
    return ConfigurationLifecycleService(
        cast(
            ConfigurationApplicationPort,
            SqlAlchemyConfigurationRepository(session),
        ),
        settings,
        publisher,
    )


ConfigurationQueryDependency = Annotated[
    ConfigurationQueryService,
    Depends(configuration_query_service),
]
ConfigurationLifecycleDependency = Annotated[
    ConfigurationLifecycleService,
    Depends(configuration_lifecycle_service),
]
