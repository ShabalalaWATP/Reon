"""Approved configuration activation and materialisation use case."""

from __future__ import annotations

from uuid import UUID

from istari_service.configuration_digest import configuration_digest
from istari_service.configuration_events import ConfigurationEventType
from istari_service.configuration_policy import may_activate
from istari_service.configuration_records import (
    ConfigurationBundleRecord,
    stored_utc,
)
from istari_service.configuration_types import ApprovalDecision, FindingSeverity
from istari_service.domain import Actor
from istari_service.errors import InvalidAdministrationChange
from istari_service.schemas.configuration import (
    ConfigurationReasonCommand,
    ConfigurationVersionDetail,
)
from istari_service.services.configuration_ports import ConfigurationActivationPort
from istari_service.services.configuration_service_base import ConfigurationServiceBase
from istari_service.services.configuration_validation_support import (
    configuration_findings,
)


class ConfigurationActivationService(
    ConfigurationServiceBase[ConfigurationActivationPort]
):
    async def activate(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        version = await self._repository.locked_version(
            version_id, payload.expected_version
        )
        bundle = await self._repository.bundle(version.id)
        self._require_activation_authority(actor, bundle)
        now = self._clock()
        if stored_utc(version.effective_from) > now:
            raise InvalidAdministrationChange(
                "The configured effective time must arrive before activation."
            )
        findings = await configuration_findings(self._repository, bundle)
        if any(item.severity is FindingSeverity.ERROR for item in findings):
            raise InvalidAdministrationChange(
                "Validate the current configuration and workflow deployment again."
            )
        await self._repository.replace_findings(version.id, findings)
        approval = bundle.approval
        if approval is None:
            raise InvalidAdministrationChange("Approval evidence is unavailable.")
        if approval.snapshot_digest != configuration_digest(bundle.specification()):
            raise InvalidAdministrationChange(
                "The approved configuration snapshot no longer matches review evidence."
            )
        superseded = await self._repository.activate(
            version,
            approval,
            actor_id=actor.id,
            reason=payload.reason,
            now=now,
        )
        await self._repository.materialise_configuration(bundle.specification(), at=now)
        await self._audit(
            actor,
            "CONFIGURATION_ACTIVATED",
            version.id,
            ["status", "activatedAt", "activeVersion"],
            "Approved configuration activated for new requests.",
        )
        if superseded is not None:
            await self._audit(
                actor,
                "CONFIGURATION_SUPERSEDED",
                superseded.id,
                ["status"],
                "Earlier active configuration superseded.",
            )
        await self._publish(
            ConfigurationEventType.ACTIVATED,
            version,
            actor,
            now,
            superseded_id=superseded.id if superseded else None,
        )
        if superseded is not None:
            await self._publish(
                ConfigurationEventType.SUPERSEDED, superseded, actor, now
            )
        return await self._detail(version)

    @staticmethod
    def _require_activation_authority(
        actor: Actor, bundle: ConfigurationBundleRecord
    ) -> None:
        version = bundle.version
        approval = bundle.approval
        if not may_activate(version.status) or approval is None:
            raise InvalidAdministrationChange(
                "This version is not approved for activation."
            )
        if approval.decision is not ApprovalDecision.APPROVED:
            raise InvalidAdministrationChange("A rejected version cannot be activated.")
        if actor.id == version.created_by_user_id:
            raise InvalidAdministrationChange(
                "The draft creator cannot activate this version."
            )
        if approval.actor_user_id == version.created_by_user_id:
            raise InvalidAdministrationChange("The approval is not independent.")
        if approval.reviewed_version + 1 != version.version:
            raise InvalidAdministrationChange(
                "The approval does not cover this version."
            )
