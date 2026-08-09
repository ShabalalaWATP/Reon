"""Fail-closed readiness for the request-routing configuration runtime."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_integrity import snapshot_evidence_is_valid
from istari_service.configuration_models import (
    ApprovedWorkflowDefinition,
    ConfigurationRegistry,
    ConfigurationVersion,
    ConfigurationWorkflowTemplate,
)
from istari_service.configuration_policy import WORKFLOW_COMPATIBILITY_KEY
from istari_service.configuration_types import ConfigurationStatus
from istari_service.repositories.configuration import SqlAlchemyConfigurationRepository
from istari_service.repositories.configuration_records import stored_utc


async def configuration_runtime_is_ready(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> bool:
    registry = await session.get(ConfigurationRegistry, 1)
    if registry is None or registry.active_version_id is None:
        return False
    version = await session.get(ConfigurationVersion, registry.active_version_id)
    effective_at = now or datetime.now(UTC)
    if (
        version is None
        or version.status is not ConfigurationStatus.ACTIVE
        or stored_utc(version.effective_from) > effective_at
    ):
        return False
    template = await session.scalar(
        select(ConfigurationWorkflowTemplate).where(
            ConfigurationWorkflowTemplate.configuration_version_id == version.id
        )
    )
    if template is None:
        return False
    specification = (
        await SqlAlchemyConfigurationRepository(session).bundle(
            version.id, version=version
        )
    ).specification()
    if not await snapshot_evidence_is_valid(session, version.id, specification):
        return False
    workflow = await session.get(
        ApprovedWorkflowDefinition,
        template.workflow_definition_id,
    )
    return bool(
        workflow is not None
        and workflow.is_available
        and workflow.compatibility_key == WORKFLOW_COMPATIBILITY_KEY
        and len(workflow.checksum) == 64
    )
