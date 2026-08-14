"""Configuration draft creation and replacement use cases."""

from __future__ import annotations

from uuid import UUID

from istari_service.configuration_policy import may_replace_draft
from istari_service.configuration_types import ConfigurationStatus
from istari_service.domain import Actor
from istari_service.errors import InvalidAdministrationChange
from istari_service.schemas.configuration import (
    ConfigurationDraftCreate,
    ConfigurationDraftReplace,
    ConfigurationVersionDetail,
)
from istari_service.services.configuration_ports import ConfigurationDraftPort
from istari_service.services.configuration_service_base import ConfigurationServiceBase


class ConfigurationDraftService(ConfigurationServiceBase[ConfigurationDraftPort]):
    async def create(
        self, actor: Actor, payload: ConfigurationDraftCreate
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        await self._validate_base(payload.based_on_version_id)
        version = await self._repository.create_draft(
            label=payload.label,
            effective_from=payload.effective_from,
            created_by_user_id=actor.id,
            based_on_version_id=payload.based_on_version_id,
            specification=payload.to_spec(),
        )
        await self._audit(
            actor,
            "CONFIGURATION_DRAFT_CREATED",
            version.id,
            ["label", "effectiveFrom", "basedOnVersionId", "snapshot"],
            "Configuration draft created.",
        )
        return await self._detail(version)

    async def replace(
        self,
        actor: Actor,
        version_id: UUID,
        payload: ConfigurationDraftReplace,
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        version = await self._repository.locked_version(
            version_id, payload.expected_version
        )
        if not may_replace_draft(version.status):
            raise InvalidAdministrationChange("Only Draft versions can be changed.")
        if payload.based_on_version_id == version.id:
            raise InvalidAdministrationChange(
                "A configuration cannot be based on itself."
            )
        await self._validate_base(payload.based_on_version_id)
        version.label = payload.label
        version.effective_from = payload.effective_from
        version.based_on_version_id = payload.based_on_version_id
        version.version += 1
        await self._repository.replace_components(version.id, payload.to_spec())
        await self._audit(
            actor,
            "CONFIGURATION_DRAFT_REPLACED",
            version.id,
            ["label", "effectiveFrom", "basedOnVersionId", "snapshot"],
            "Configuration draft snapshot replaced.",
        )
        return await self._detail(version)

    async def _validate_base(self, version_id: UUID | None) -> None:
        if version_id is None:
            return
        base = await self._repository.get_version(version_id)
        if base.status is ConfigurationStatus.DRAFT:
            raise InvalidAdministrationChange(
                "Create a draft from an immutable configuration version."
            )
