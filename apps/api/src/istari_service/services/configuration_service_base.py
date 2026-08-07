"""Shared access, audit and event controls for configuration use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from istari_service.admin_audit import append_admin_event
from istari_service.config import Settings
from istari_service.configuration_events import (
    ConfigurationEventPublisher,
    ConfigurationEventType,
    ConfigurationLifecycleEvent,
    NullConfigurationEventPublisher,
)
from istari_service.configuration_models import ConfigurationVersion
from istari_service.configuration_policy import can_administer_configuration
from istari_service.configuration_views import version_detail
from istari_service.domain import Actor
from istari_service.errors import (
    AdministrationAccessDenied,
    AdministrationUnavailable,
)
from istari_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from istari_service.schemas.configuration import ConfigurationVersionDetail


class ConfigurationServiceBase:
    def __init__(
        self,
        repository: SqlAlchemyConfigurationRepository,
        settings: Settings,
        publisher: ConfigurationEventPublisher | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher or NullConfigurationEventPublisher()
        self._clock = clock or (lambda: datetime.now(UTC))

    def authorise(self, actor: Actor) -> None:
        if not self._settings.configuration_admin_enabled:
            raise AdministrationUnavailable()
        if not can_administer_configuration(actor.role):
            raise AdministrationAccessDenied()

    async def _audit(
        self,
        actor: Actor,
        action: str,
        version_id: UUID,
        changed_fields: list[str],
        summary: str,
    ) -> None:
        await append_admin_event(
            self._repository.session,
            actor_id=actor.id,
            action=action,
            target_type="CONFIGURATION_VERSION",
            target_id=version_id,
            changed_fields=changed_fields,
            summary=summary,
        )

    async def _publish(
        self,
        event_type: ConfigurationEventType,
        version: ConfigurationVersion,
        actor: Actor,
        occurred_at: datetime,
        *,
        superseded_id: UUID | None = None,
    ) -> None:
        await self._publisher.publish(
            ConfigurationLifecycleEvent(
                type=event_type,
                configuration_version_id=version.id,
                configuration_sequence=version.sequence,
                actor_user_id=actor.id,
                occurred_at=occurred_at,
                source_version=version.version,
                superseded_configuration_version_id=superseded_id,
            )
        )

    async def _detail(
        self, version: ConfigurationVersion
    ) -> ConfigurationVersionDetail:
        await self._repository.session.flush()
        await self._repository.session.refresh(version)
        return version_detail(
            await self._repository.bundle(version.id, version=version)
        )
