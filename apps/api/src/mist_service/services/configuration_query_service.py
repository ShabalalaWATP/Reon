"""Read-only configuration history, preview and as-of use cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from mist_service.config import Settings
from mist_service.configuration_digest import configuration_digest
from mist_service.configuration_projection import preview_configuration_schedule
from mist_service.configuration_records import ConfigurationBundleRecord, stored_utc
from mist_service.configuration_views import (
    organisation_snapshot,
    preview_views,
    version_detail,
    version_summary,
    workflow_view,
)
from mist_service.domain import Actor
from mist_service.errors import ObjectNotFound
from mist_service.schemas.configuration import (
    ApprovedWorkflowDefinitionList,
    ConfigurationOrganisationSnapshot,
    ConfigurationPreview,
    ConfigurationVersionDetail,
    ConfigurationVersionList,
)
from mist_service.services.configuration_ports import ConfigurationQueryPort
from mist_service.services.configuration_service_base import (
    ConfigurationAccessService,
)


class ConfigurationQueryService(ConfigurationAccessService):
    def __init__(self, repository: ConfigurationQueryPort, settings: Settings) -> None:
        super().__init__(settings)
        self._repository = repository

    async def list_versions(self, actor: Actor) -> ConfigurationVersionList:
        self.authorise(actor)
        versions = await self._repository.list_versions()
        return ConfigurationVersionList(
            items=[version_summary(version) for version in versions]
        )

    async def get_version(
        self, actor: Actor, version_id: UUID
    ) -> ConfigurationVersionDetail:
        self.authorise(actor)
        return version_detail(await self._repository.bundle(version_id))

    async def active(self, actor: Actor) -> ConfigurationVersionDetail:
        self.authorise(actor)
        bundle = await self._repository.active_bundle()
        if bundle is None:
            raise ObjectNotFound()
        return version_detail(bundle)

    async def workflow_definitions(
        self, actor: Actor
    ) -> ApprovedWorkflowDefinitionList:
        self.authorise(actor)
        definitions = await self._repository.list_workflows()
        return ApprovedWorkflowDefinitionList(
            items=[workflow_view(definition) for definition in definitions]
        )

    async def preview(
        self,
        actor: Actor,
        version_id: UUID,
        *,
        at: datetime | None = None,
    ) -> ConfigurationPreview:
        self.authorise(actor)
        candidate = await self._repository.bundle(version_id)
        base = await self._comparison_base(candidate.version.based_on_version_id)
        specification = candidate.specification()
        comparison = base.specification() if base is not None else None
        unit_ids = {item.unit_id for item in specification.units}
        if comparison is not None:
            unit_ids.update(item.unit_id for item in comparison.units)
        staffing = await self._repository.staffing_counts(unit_ids)
        changes = preview_configuration_schedule(
            comparison,
            specification,
            starts_at=at or stored_utc(candidate.version.effective_from),
            staffing=staffing,
        )
        return ConfigurationPreview(
            version_id=version_id,
            compared_with_version_id=base.version.id if base else None,
            snapshot_digest=configuration_digest(specification),
            changes=preview_views(changes),
        )

    async def organisation(
        self,
        actor: Actor,
        version_id: UUID,
        *,
        at: datetime | None = None,
    ) -> ConfigurationOrganisationSnapshot:
        self.authorise(actor)
        bundle = await self._repository.bundle(version_id)
        effective_at = at or datetime.now(UTC)
        return organisation_snapshot(version_id, bundle.specification(), effective_at)

    async def _comparison_base(
        self, version_id: UUID | None
    ) -> ConfigurationBundleRecord | None:
        if version_id is not None:
            return await self._repository.bundle(version_id)
        return None
