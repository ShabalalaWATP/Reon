"""API projections for immutable configuration records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from istari_service.configuration_models import (
    ApprovedWorkflowDefinition,
    ConfigurationVersion,
)
from istari_service.configuration_projection import (
    active_parents,
    active_units,
    mappings_for_unit,
)
from istari_service.configuration_types import ConfigurationDraftSpec, PreviewChange
from istari_service.repositories.configuration_records import (
    ConfigurationBundle,
    stored_utc,
)
from istari_service.schemas.configuration import (
    ApprovedWorkflowDefinitionView,
    CandidateGroupInput,
    ConfigurationApprovalView,
    ConfigurationOrganisationSnapshot,
    ConfigurationVersionDetail,
    ConfigurationVersionSummary,
    HierarchyEdgeInput,
    OrganisationSnapshotUnit,
    PreviewChangeView,
    UnitRevisionInput,
    ValidationFindingView,
    WorkflowTemplateInput,
)


def version_summary(version: ConfigurationVersion) -> ConfigurationVersionSummary:
    return ConfigurationVersionSummary(
        id=version.id,
        sequence=version.sequence,
        label=version.label,
        status=version.status,
        effective_from=stored_utc(version.effective_from),
        created_by_user_id=version.created_by_user_id,
        based_on_version_id=version.based_on_version_id,
        version=version.version,
        created_at=stored_utc(version.created_at),
        updated_at=stored_utc(version.updated_at),
    )


def version_detail(bundle: ConfigurationBundle) -> ConfigurationVersionDetail:
    version = bundle.version
    specification = bundle.specification()
    approval = None
    if bundle.approval is not None:
        approval = ConfigurationApprovalView(
            actor_user_id=bundle.approval.actor_user_id,
            decision=bundle.approval.decision,
            reviewed_version=bundle.approval.reviewed_version,
            reason=bundle.approval.reason,
            created_at=stored_utc(bundle.approval.created_at),
        )
    return ConfigurationVersionDetail(
        **version_summary(version).model_dump(),
        reason=version.reason,
        validated_at=_optional_utc(version.validated_at),
        submitted_at=_optional_utc(version.submitted_at),
        activated_at=_optional_utc(version.activated_at),
        rejected_at=_optional_utc(version.rejected_at),
        units=[UnitRevisionInput.model_validate(item) for item in specification.units],
        edges=[HierarchyEdgeInput.model_validate(item) for item in specification.edges],
        candidate_groups=[
            CandidateGroupInput.model_validate(item)
            for item in specification.candidate_groups
        ],
        workflow_template=WorkflowTemplateInput.model_validate(
            specification.workflow_template
        ),
        findings=[
            ValidationFindingView.model_validate(item) for item in bundle.findings
        ],
        approval=approval,
    )


def workflow_view(
    definition: ApprovedWorkflowDefinition,
) -> ApprovedWorkflowDefinitionView:
    return ApprovedWorkflowDefinitionView(
        id=definition.id,
        process_id=definition.process_id,
        process_definition_key=definition.process_definition_key,
        process_version=definition.process_version,
        compatibility_key=definition.compatibility_key,
        checksum=definition.checksum,
        approved_at=stored_utc(definition.approved_at),
    )


def preview_views(changes: list[PreviewChange]) -> list[PreviewChangeView]:
    return [PreviewChangeView.model_validate(change) for change in changes]


def organisation_snapshot(
    version_id: UUID,
    specification: ConfigurationDraftSpec,
    at: datetime,
) -> ConfigurationOrganisationSnapshot:
    units = active_units(specification, at)
    parents = active_parents(specification, at)
    views = [
        OrganisationSnapshotUnit(
            unit_id=unit_id,
            code=unit.code,
            name=unit.name,
            kind=unit.kind,
            parent_unit_id=parents.get(unit_id),
            routing_enabled=unit.routing_enabled,
            candidate_groups=mappings_for_unit(specification.candidate_groups, unit_id),
        )
        for unit_id, unit in units.items()
    ]
    return ConfigurationOrganisationSnapshot(
        version_id=version_id,
        as_of=at,
        units=sorted(views, key=lambda item: (item.code, str(item.unit_id))),
    )


def _optional_utc(value: datetime | None) -> datetime | None:
    return stored_utc(value) if value is not None else None
