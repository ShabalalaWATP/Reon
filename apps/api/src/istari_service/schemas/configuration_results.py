"""Configuration lifecycle, projection and pinning response contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from istari_service.configuration_types import (
    ApprovalDecision,
    CandidateGroupPurpose,
    ConfigurationStatus,
    FindingSeverity,
    PreviewChangeType,
)
from istari_service.organisation_models import OrganisationKind
from istari_service.schemas.common import ApiModel
from istari_service.schemas.configuration_inputs import (
    CandidateGroupInput,
    HierarchyEdgeInput,
    UnitRevisionInput,
    WorkflowTemplateInput,
)


class ValidationFindingView(ApiModel):
    severity: FindingSeverity
    code: str
    message: str
    path: str
    unit_id: UUID | None


class PreviewChangeView(ApiModel):
    type: PreviewChangeType
    unit_id: UUID
    code: str
    message: str
    effective_at: datetime


class ConfigurationApprovalView(ApiModel):
    actor_user_id: UUID
    decision: ApprovalDecision
    reviewed_version: int
    snapshot_digest: str
    reason: str
    created_at: datetime


class ConfigurationVersionSummary(ApiModel):
    id: UUID
    sequence: int
    label: str
    status: ConfigurationStatus
    effective_from: datetime
    created_by_user_id: UUID
    based_on_version_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class ConfigurationVersionList(ApiModel):
    items: list[ConfigurationVersionSummary]


class ConfigurationVersionDetail(ConfigurationVersionSummary):
    reason: str | None
    validated_at: datetime | None
    submitted_at: datetime | None
    activated_at: datetime | None
    rejected_at: datetime | None
    units: list[UnitRevisionInput]
    edges: list[HierarchyEdgeInput]
    candidate_groups: list[CandidateGroupInput]
    workflow_template: WorkflowTemplateInput
    findings: list[ValidationFindingView]
    approval: ConfigurationApprovalView | None


class ConfigurationPreview(ApiModel):
    version_id: UUID
    compared_with_version_id: UUID | None
    snapshot_digest: str
    changes: list[PreviewChangeView]


class OrganisationSnapshotUnit(ApiModel):
    unit_id: UUID
    code: str
    name: str
    kind: OrganisationKind
    parent_unit_id: UUID | None
    routing_enabled: bool
    candidate_groups: dict[CandidateGroupPurpose, str]


class ConfigurationOrganisationSnapshot(ApiModel):
    version_id: UUID
    as_of: datetime
    units: list[OrganisationSnapshotUnit]


class ApprovedWorkflowDefinitionView(ApiModel):
    id: UUID
    process_id: str
    process_definition_key: str
    process_version: int
    compatibility_key: str
    checksum: str
    approved_at: datetime


class ApprovedWorkflowDefinitionList(ApiModel):
    items: list[ApprovedWorkflowDefinitionView]


class RequestConfigurationPinView(ApiModel):
    request_id: UUID
    configuration_version_id: UUID
    workflow_template_id: UUID
    organisation_root_id: UUID
    form_version: str
    notification_policy_version: str
