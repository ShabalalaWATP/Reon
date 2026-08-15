"""SQLAlchemy adapter for immutable configuration-version administration."""

from __future__ import annotations

from collections.abc import Sequence, Set
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.admin_audit import append_admin_event
from mist_service.configuration_materialisation import materialise_configuration_units
from mist_service.configuration_models import (
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
from mist_service.configuration_records import (
    ConfigurationApprovalRecord,
    ConfigurationVersionRecord,
)
from mist_service.configuration_types import (
    ApprovalDecision,
    ConfigurationDraftSpec,
    ConfigurationStatus,
    StaffingCount,
    ValidationFinding,
)
from mist_service.errors import (
    InvalidAdministrationChange,
    ObjectNotFound,
    StaleVersion,
)
from mist_service.repositories.configuration_mutations import (
    replace_configuration_components,
    replace_configuration_findings,
)
from mist_service.repositories.configuration_records import ConfigurationBundle
from mist_service.repositories.configuration_staffing import load_staffing_counts


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

    async def create_draft(
        self,
        *,
        label: str,
        effective_from: datetime,
        created_by_user_id: UUID,
        based_on_version_id: UUID | None,
        specification: ConfigurationDraftSpec,
    ) -> ConfigurationVersion:
        version = ConfigurationVersion(
            sequence=await self.next_sequence(),
            label=label,
            status=ConfigurationStatus.DRAFT,
            effective_from=effective_from,
            created_by_user_id=created_by_user_id,
            based_on_version_id=based_on_version_id,
            reason=None,
        )
        self.session.add(version)
        await self.session.flush()
        await self.replace_components(version.id, specification)
        return version

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
        self,
        version_id: UUID,
        *,
        version: ConfigurationVersionRecord | None = None,
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
        await replace_configuration_components(self.session, version_id, specification)

    async def replace_findings(
        self, version_id: UUID, findings: list[ValidationFinding]
    ) -> None:
        await replace_configuration_findings(self.session, version_id, findings)

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
        version: ConfigurationVersionRecord,
        *,
        actor_id: UUID,
        decision: ApprovalDecision,
        reason: str,
        snapshot_digest: str,
    ) -> ConfigurationApproval:
        approval = ConfigurationApproval(
            configuration_version_id=version.id,
            actor_user_id=actor_id,
            decision=decision,
            reviewed_version=version.version,
            snapshot_digest=snapshot_digest,
            reason=reason,
        )
        self.session.add(approval)
        await self.session.flush()
        return approval

    async def activate(
        self,
        version: ConfigurationVersionRecord,
        approval: ConfigurationApprovalRecord,
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
        # PostgreSQL validates the activation evidence against the persisted
        # candidate and registry state. Flush those changes before inserting
        # the evidence row so the trigger observes the approved transition.
        await self.session.flush()
        self.session.add(
            ConfigurationActivation(
                configuration_version_id=version.id,
                approval_id=approval.id,
                activated_by_user_id=actor_id,
                superseded_version_id=active_id,
                reason=reason,
                snapshot_digest=approval.snapshot_digest,
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

    async def refresh_version(
        self, version: ConfigurationVersionRecord
    ) -> ConfigurationVersionRecord:
        await self.session.flush()
        await self.session.refresh(version)
        return version

    async def append_configuration_audit(
        self,
        *,
        actor_id: UUID,
        action: str,
        version_id: UUID,
        changed_fields: Sequence[str],
        summary: str,
    ) -> None:
        await append_admin_event(
            self.session,
            actor_id=actor_id,
            action=action,
            target_type="CONFIGURATION_VERSION",
            target_id=version_id,
            changed_fields=list(changed_fields),
            summary=summary,
        )

    async def staffing_counts(self, unit_ids: Set[UUID]) -> dict[UUID, StaffingCount]:
        return await load_staffing_counts(self.session, set(unit_ids))

    async def materialise_configuration(
        self, specification: ConfigurationDraftSpec, *, at: datetime
    ) -> None:
        await materialise_configuration_units(self.session, specification, at=at)
