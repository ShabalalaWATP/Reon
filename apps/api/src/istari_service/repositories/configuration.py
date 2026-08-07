"""SQLAlchemy adapter for immutable configuration-version administration."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_models import (
    ApprovedWorkflowDefinition,
    ConfigurationActivation,
    ConfigurationApproval,
    ConfigurationCandidateGroup,
    ConfigurationHierarchyEdge,
    ConfigurationRegistry,
    ConfigurationUnitRevision,
    ConfigurationValidationFinding,
    ConfigurationVersion,
    ConfigurationWorkflowTemplate,
)
from istari_service.configuration_policy import WORKFLOW_SCHEMA_DIGEST
from istari_service.configuration_types import (
    ApprovalDecision,
    ConfigurationDraftSpec,
    ConfigurationStatus,
    ValidationFinding,
)
from istari_service.errors import (
    InvalidAdministrationChange,
    ObjectNotFound,
    StaleVersion,
)
from istari_service.repositories.configuration_records import ConfigurationBundle


class SqlAlchemyConfigurationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_versions(self) -> list[ConfigurationVersion]:
        return list(
            await self.session.scalars(
                select(ConfigurationVersion).order_by(
                    ConfigurationVersion.sequence.desc(), ConfigurationVersion.id
                )
            )
        )

    async def next_sequence(self) -> int:
        registry = await self.lock_registry()
        sequence = registry.next_sequence
        registry.next_sequence += 1
        return sequence

    async def lock_registry(self) -> ConfigurationRegistry:
        registry = await self.session.scalar(
            select(ConfigurationRegistry)
            .where(ConfigurationRegistry.id == 1)
            .with_for_update()
        )
        if registry is None:
            raise RuntimeError("the configuration registry is unavailable")
        return registry

    async def get_version(
        self, version_id: UUID, *, lock: bool = False
    ) -> ConfigurationVersion:
        statement = select(ConfigurationVersion).where(
            ConfigurationVersion.id == version_id
        )
        if lock:
            statement = statement.with_for_update()
        version = await self.session.scalar(statement)
        if version is None:
            raise ObjectNotFound()
        return version

    async def locked_version(
        self, version_id: UUID, expected_version: int
    ) -> ConfigurationVersion:
        version = await self.get_version(version_id, lock=True)
        if version.version != expected_version:
            raise StaleVersion()
        return version

    async def bundle(
        self, version_id: UUID, *, version: ConfigurationVersion | None = None
    ) -> ConfigurationBundle:
        stored = version or await self.get_version(version_id)
        units = tuple(
            await self.session.scalars(
                select(ConfigurationUnitRevision)
                .where(ConfigurationUnitRevision.configuration_version_id == version_id)
                .order_by(
                    ConfigurationUnitRevision.code,
                    ConfigurationUnitRevision.effective_from,
                    ConfigurationUnitRevision.id,
                )
            )
        )
        edges = tuple(
            await self.session.scalars(
                select(ConfigurationHierarchyEdge)
                .where(
                    ConfigurationHierarchyEdge.configuration_version_id == version_id
                )
                .order_by(
                    ConfigurationHierarchyEdge.child_unit_id,
                    ConfigurationHierarchyEdge.effective_from,
                )
            )
        )
        groups = tuple(
            await self.session.scalars(
                select(ConfigurationCandidateGroup)
                .where(
                    ConfigurationCandidateGroup.configuration_version_id == version_id
                )
                .order_by(
                    ConfigurationCandidateGroup.unit_id,
                    ConfigurationCandidateGroup.purpose,
                )
            )
        )
        template = await self.session.scalar(
            select(ConfigurationWorkflowTemplate).where(
                ConfigurationWorkflowTemplate.configuration_version_id == version_id
            )
        )
        if template is None:
            raise RuntimeError("the configuration workflow template is unavailable")
        findings = tuple(
            await self.session.scalars(
                select(ConfigurationValidationFinding)
                .where(
                    ConfigurationValidationFinding.configuration_version_id
                    == version_id
                )
                .order_by(
                    ConfigurationValidationFinding.severity,
                    ConfigurationValidationFinding.code,
                    ConfigurationValidationFinding.unit_id,
                )
            )
        )
        approval = await self.session.scalar(
            select(ConfigurationApproval).where(
                ConfigurationApproval.configuration_version_id == version_id
            )
        )
        return ConfigurationBundle(
            stored, units, edges, groups, template, findings, approval
        )

    async def replace_components(
        self, version_id: UUID, specification: ConfigurationDraftSpec
    ) -> None:
        version = await self.get_version(version_id, lock=True)
        if version.status is not ConfigurationStatus.DRAFT:
            raise InvalidAdministrationChange(
                "Only Draft configuration components can be replaced."
            )
        for model in (
            ConfigurationValidationFinding,
            ConfigurationCandidateGroup,
            ConfigurationHierarchyEdge,
            ConfigurationUnitRevision,
            ConfigurationWorkflowTemplate,
        ):
            await self.session.execute(
                delete(model).where(model.configuration_version_id == version_id)
            )
        self.session.add_all(
            ConfigurationUnitRevision(
                configuration_version_id=version_id,
                unit_id=item.unit_id,
                code=item.code,
                name=item.name,
                kind=item.kind,
                effective_from=item.effective_from,
                effective_until=item.effective_until,
                routing_enabled=item.routing_enabled,
                minimum_managers=item.minimum_managers,
                minimum_analysts=item.minimum_analysts,
            )
            for item in specification.units
        )
        self.session.add_all(
            ConfigurationHierarchyEdge(
                configuration_version_id=version_id,
                parent_unit_id=item.parent_unit_id,
                child_unit_id=item.child_unit_id,
                effective_from=item.effective_from,
                effective_until=item.effective_until,
            )
            for item in specification.edges
        )
        self.session.add_all(
            ConfigurationCandidateGroup(
                configuration_version_id=version_id,
                unit_id=item.unit_id,
                purpose=item.purpose,
                candidate_group=item.candidate_group,
            )
            for item in specification.candidate_groups
        )
        template = specification.workflow_template
        self.session.add(
            ConfigurationWorkflowTemplate(
                configuration_version_id=version_id,
                schema_id=template.schema_id,
                schema_digest=WORKFLOW_SCHEMA_DIGEST,
                form_version=template.form_version,
                notification_policy_version=template.notification_policy_version,
                organisation_root_id=template.organisation_root_id,
                route_depth=template.route_depth,
                core_fields=list(template.core_fields),
                service_categories=list(template.service_categories),
                product_types=list(template.product_types),
                task_labels=dict(template.task_labels),
                allowed_outcomes={
                    key: list(values)
                    for key, values in template.allowed_outcomes.items()
                },
                reminder_days=list(template.reminder_days),
                artefact_types=list(template.artefact_types),
                approved_link_domains=list(template.approved_link_domains),
                workflow_definition_id=template.workflow_definition_id,
            )
        )
        await self.session.flush()

    async def replace_findings(
        self, version_id: UUID, findings: list[ValidationFinding]
    ) -> None:
        await self.session.execute(
            delete(ConfigurationValidationFinding).where(
                ConfigurationValidationFinding.configuration_version_id == version_id
            )
        )
        self.session.add_all(
            ConfigurationValidationFinding(
                configuration_version_id=version_id,
                severity=item.severity,
                code=item.code,
                message=item.message,
                path=item.path,
                unit_id=item.unit_id,
            )
            for item in findings
        )
        await self.session.flush()

    async def approved_workflow(
        self, workflow_id: UUID
    ) -> ApprovedWorkflowDefinition | None:
        return await self.session.get(ApprovedWorkflowDefinition, workflow_id)

    async def list_workflows(self) -> list[ApprovedWorkflowDefinition]:
        return list(
            await self.session.scalars(
                select(ApprovedWorkflowDefinition)
                .where(ApprovedWorkflowDefinition.is_available.is_(True))
                .order_by(
                    ApprovedWorkflowDefinition.process_id,
                    ApprovedWorkflowDefinition.process_version,
                )
            )
        )

    async def create_approval(
        self,
        version: ConfigurationVersion,
        *,
        actor_id: UUID,
        decision: ApprovalDecision,
        reason: str,
    ) -> ConfigurationApproval:
        approval = ConfigurationApproval(
            configuration_version_id=version.id,
            actor_user_id=actor_id,
            decision=decision,
            reviewed_version=version.version,
            reason=reason,
        )
        self.session.add(approval)
        await self.session.flush()
        return approval

    async def activate(
        self,
        version: ConfigurationVersion,
        approval: ConfigurationApproval,
        *,
        actor_id: UUID,
        reason: str,
        now: datetime,
    ) -> ConfigurationVersion | None:
        registry = await self.lock_registry()
        active_id = registry.active_version_id
        if version.based_on_version_id != active_id:
            raise StaleVersion()
        active: ConfigurationVersion | None = None
        if active_id is not None:
            active = await self.get_version(active_id, lock=True)
            active.status = ConfigurationStatus.SUPERSEDED
            active.version += 1
            await self.session.flush()
        version.status = ConfigurationStatus.ACTIVE
        version.activated_at = now
        version.version += 1
        registry.active_version_id = version.id
        registry.version += 1
        self.session.add(
            ConfigurationActivation(
                configuration_version_id=version.id,
                approval_id=approval.id,
                activated_by_user_id=actor_id,
                superseded_version_id=active_id,
                reason=reason,
                activated_at=now,
            )
        )
        await self.session.flush()
        return active

    async def active_bundle(self) -> ConfigurationBundle | None:
        registry = await self.session.get(ConfigurationRegistry, 1)
        if registry is None or registry.active_version_id is None:
            return None
        return await self.bundle(registry.active_version_id)
