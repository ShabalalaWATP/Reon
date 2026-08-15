"""Shared access, audit and event controls for configuration use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from mist_service.config import Settings
from mist_service.configuration_events import (
    ConfigurationEventPublisher,
    ConfigurationEventType,
    ConfigurationLifecycleEvent,
    NullConfigurationEventPublisher,
)
from mist_service.configuration_policy import can_administer_configuration
from mist_service.configuration_records import ConfigurationVersionRecord
from mist_service.configuration_views import version_detail
from mist_service.domain import Actor
from mist_service.errors import (
    AdministrationAccessDenied,
    AdministrationUnavailable,
)
from mist_service.schemas.configuration import ConfigurationVersionDetail
from mist_service.services.configuration_ports import ConfigurationCommandCorePort


class ConfigurationAccessService:
    """Shared feature-flag and role authorisation with no persistence dependency."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def authorise(self, actor: Actor) -> None:
        if not self._settings.configuration_admin_enabled:
            raise AdministrationUnavailable()
        if not can_administer_configuration(actor.role):
            raise AdministrationAccessDenied()


class ConfigurationServiceBase[RepositoryT: ConfigurationCommandCorePort](
    ConfigurationAccessService
):
    def __init__(
        self,
        repository: RepositoryT,
        settings: Settings,
        publisher: ConfigurationEventPublisher | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(settings)
        self._repository = repository
        self._publisher = publisher or NullConfigurationEventPublisher()
        self._clock = clock or (lambda: datetime.now(UTC))

    async def _audit(
        self,
        actor: Actor,
        action: str,
        version_id: UUID,
        changed_fields: list[str],
        summary: str,
    ) -> None:
        await self._repository.append_configuration_audit(
            actor_id=actor.id,
            action=action,
            version_id=version_id,
            changed_fields=changed_fields,
            summary=summary,
        )

    async def _publish(
        self,
        event_type: ConfigurationEventType,
        version: ConfigurationVersionRecord,
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
        self, version: ConfigurationVersionRecord
    ) -> ConfigurationVersionDetail:
        await self._repository.refresh_version(version)
        return version_detail(await self._repository.bundle(version.id))
