"""Configuration validation and submission use cases."""

from __future__ import annotations

from uuid import UUID

from istari_service.configuration_events import ConfigurationEventType
from istari_service.configuration_policy import may_submit, may_validate
from istari_service.configuration_types import ConfigurationStatus, FindingSeverity
from istari_service.domain import Actor
from istari_service.errors import InvalidAdministrationChange
from istari_service.schemas.configuration import (
    ConfigurationReasonCommand,
    ConfigurationVersionCommand,
    ConfigurationVersionDetail,
)
from istari_service.services.configuration_service_base import ConfigurationServiceBase
from istari_service.services.configuration_validation_support import (
    configuration_findings,
)


class ConfigurationValidationService(ConfigurationServiceBase):
    async def validate(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationVersionCommand,
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        version = await self._repository.locked_version(
            version_id, payload.expected_version
        )
        if not may_validate(version.status):
            raise InvalidAdministrationChange("This version cannot be validated.")
        bundle = await self._repository.bundle(version.id, version=version)
        findings = await configuration_findings(self._repository, bundle)
        await self._repository.replace_findings(version.id, findings)
        has_errors = any(item.severity is FindingSeverity.ERROR for item in findings)
        version.status = (
            ConfigurationStatus.DRAFT if has_errors else ConfigurationStatus.VALIDATED
        )
        version.validated_at = None if has_errors else self._clock()
        version.version += 1
        await self._audit(
            actor,
            "CONFIGURATION_VALIDATED",
            version.id,
            ["status", "findings", "validatedAt"],
            "Configuration validation completed.",
        )
        return await self._detail(version)

    async def submit(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        version = await self._repository.locked_version(
            version_id, payload.expected_version
        )
        if not may_submit(version.status):
            raise InvalidAdministrationChange(
                "Only a Validated version can be submitted."
            )
        now = self._clock()
        version.status = ConfigurationStatus.AWAITING_APPROVAL
        version.reason = payload.reason
        version.submitted_at = now
        version.version += 1
        await self._audit(
            actor,
            "CONFIGURATION_SUBMITTED",
            version.id,
            ["status", "reason", "submittedAt"],
            "Configuration submitted for independent approval.",
        )
        await self._publish(ConfigurationEventType.AWAITING_REVIEW, version, actor, now)
        return await self._detail(version)
