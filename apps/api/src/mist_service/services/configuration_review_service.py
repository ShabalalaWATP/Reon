"""Independent approval and rejection operations for configuration versions."""

from __future__ import annotations

from uuid import UUID

from mist_service.configuration_digest import configuration_digest
from mist_service.configuration_events import ConfigurationEventType
from mist_service.configuration_policy import actor_is_independent, may_review
from mist_service.configuration_types import ApprovalDecision, ConfigurationStatus
from mist_service.domain import Actor
from mist_service.errors import InvalidAdministrationChange
from mist_service.schemas.configuration import (
    ConfigurationReasonCommand,
    ConfigurationVersionDetail,
)
from mist_service.services.configuration_ports import ConfigurationReviewPort
from mist_service.services.configuration_service_base import (
    ConfigurationServiceBase,
)


class ConfigurationReviewOperations(ConfigurationServiceBase[ConfigurationReviewPort]):
    async def approve(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
    ) -> ConfigurationVersionDetail:
        return await self._review(actor, version_id, payload, ApprovalDecision.APPROVED)

    async def reject(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
    ) -> ConfigurationVersionDetail:
        return await self._review(actor, version_id, payload, ApprovalDecision.REJECTED)

    async def _review(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationReasonCommand,
        decision: ApprovalDecision,
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        version = await self._repository.locked_version(
            version_id, payload.expected_version
        )
        if not may_review(version.status):
            raise InvalidAdministrationChange("This version is not awaiting approval.")
        if not actor_is_independent(actor.id, version.created_by_user_id):
            raise InvalidAdministrationChange(
                "A different Platform Administrator must review this version."
            )
        bundle = await self._repository.bundle(version.id)
        if bundle.approval is not None:
            raise InvalidAdministrationChange("This version already has a decision.")
        await self._repository.create_approval(
            version,
            actor_id=actor.id,
            decision=decision,
            reason=payload.reason,
            snapshot_digest=configuration_digest(bundle.specification()),
        )
        now = self._clock()
        if decision is ApprovalDecision.REJECTED:
            version.status = ConfigurationStatus.REJECTED
            version.rejected_at = now
        version.version += 1
        action = (
            "CONFIGURATION_APPROVED"
            if decision is ApprovalDecision.APPROVED
            else "CONFIGURATION_REJECTED"
        )
        await self._audit(
            actor,
            action,
            version.id,
            ["approval", "status"],
            "Independent configuration decision recorded.",
        )
        if decision is ApprovalDecision.REJECTED:
            await self._publish(ConfigurationEventType.REJECTED, version, actor, now)
        return await self._detail(version)
