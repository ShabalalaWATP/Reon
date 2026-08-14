"""Immutable request-to-configuration pin persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_integrity import snapshot_evidence_is_valid
from istari_service.configuration_models import (
    ApprovedWorkflowDefinition,
    ConfigurationRegistry,
    ConfigurationVersion,
    RequestConfigurationPin,
)
from istari_service.configuration_projection import active_units
from istari_service.configuration_records import stored_utc
from istari_service.configuration_request_policy import (
    build_request_policy_snapshot,
)
from istari_service.configuration_types import ConfigurationStatus
from istari_service.errors import ObjectNotFound
from istari_service.models import ServiceRequest
from istari_service.organisation_models import OrganisationUnit
from istari_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from istari_service.repositories.configuration_staffing import load_staffing_counts


class SqlAlchemyConfigurationPinRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def pin_request(
        self, request_id: UUID, *, now: datetime | None = None
    ) -> RequestConfigurationPin:
        request = await self.session.scalar(
            select(ServiceRequest)
            .where(ServiceRequest.id == request_id)
            .with_for_update()
        )
        if request is None:
            raise ObjectNotFound()
        existing = await self.session.scalar(
            select(RequestConfigurationPin).where(
                RequestConfigurationPin.request_id == request_id
            )
        )
        if existing is not None:
            return existing
        effective_at = now or datetime.now(UTC)
        registry = await self.session.scalar(
            select(ConfigurationRegistry)
            .where(ConfigurationRegistry.id == 1)
            .with_for_update()
        )
        if registry is None or registry.active_version_id is None:
            raise ObjectNotFound()
        version = await self.session.get(
            ConfigurationVersion, registry.active_version_id
        )
        if (
            version is None
            or version.status is not ConfigurationStatus.ACTIVE
            or stored_utc(version.effective_from) > effective_at
        ):
            raise ObjectNotFound()
        bundle = await SqlAlchemyConfigurationRepository(self.session).bundle(
            version.id,
            version=version,
        )
        template = bundle.workflow_template
        workflow = await self.session.get(
            ApprovedWorkflowDefinition, template.workflow_definition_id
        )
        if workflow is None or not workflow.is_available:
            raise RuntimeError("the active workflow definition is unavailable")
        specification = bundle.specification()
        if not await snapshot_evidence_is_valid(
            self.session, version.id, specification
        ):
            raise RuntimeError("the active configuration approval evidence is invalid")
        unit_ids = set(active_units(specification, effective_at))
        staffing = await load_staffing_counts(self.session, unit_ids)
        sort_orders: dict[UUID, int] = {
            unit_id: int(sort_order)
            for unit_id, sort_order in (
                await self.session.execute(
                    select(OrganisationUnit.id, OrganisationUnit.sort_order).where(
                        OrganisationUnit.id.in_(unit_ids)
                    )
                )
            ).all()
        }
        policy_snapshot = build_request_policy_snapshot(
            specification,
            at=effective_at,
            staffing=staffing,
            sort_orders=sort_orders,
        )
        pin = RequestConfigurationPin(
            request_id=request_id,
            configuration_version_id=version.id,
            workflow_template_id=template.id,
            organisation_root_id=template.organisation_root_id,
            form_version=template.form_version,
            notification_policy_version=template.notification_policy_version,
            snapshot={
                "configurationSequence": version.sequence,
                "workflowSchemaDigest": template.schema_digest,
                "processId": workflow.process_id,
                "processVersion": workflow.process_version,
                "processChecksum": workflow.checksum,
                **policy_snapshot,
            },
        )
        self.session.add(pin)
        await self.session.flush()
        return pin
