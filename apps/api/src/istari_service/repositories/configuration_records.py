"""Persistence records mapped to immutable configuration specifications."""

from __future__ import annotations

from dataclasses import dataclass

from istari_service.configuration_models import (
    ApprovedWorkflowDefinition,
    ConfigurationCandidateGroup,
    ConfigurationHierarchyEdge,
    ConfigurationUnitRevision,
    ConfigurationWorkflowTemplate,
)
from istari_service.configuration_records import (
    ConfigurationApprovalRecord,
    ConfigurationVersionRecord,
    ValidationFindingRecord,
    stored_utc,
)
from istari_service.configuration_types import (
    ApprovedWorkflowSpec,
    CandidateGroupSpec,
    ConfigurationDraftSpec,
    HierarchyEdgeSpec,
    UnitRevisionSpec,
    WorkflowTemplateSpec,
)


@dataclass(frozen=True, slots=True)
class ConfigurationBundle:
    version: ConfigurationVersionRecord
    units: tuple[ConfigurationUnitRevision, ...]
    edges: tuple[ConfigurationHierarchyEdge, ...]
    candidate_groups: tuple[ConfigurationCandidateGroup, ...]
    workflow_template: ConfigurationWorkflowTemplate
    findings: tuple[ValidationFindingRecord, ...]
    approval: ConfigurationApprovalRecord | None

    def specification(self) -> ConfigurationDraftSpec:
        template = self.workflow_template
        return ConfigurationDraftSpec(
            units=tuple(
                UnitRevisionSpec(
                    item.unit_id,
                    item.code,
                    item.name,
                    item.kind,
                    stored_utc(item.effective_from),
                    stored_utc(item.effective_until)
                    if item.effective_until is not None
                    else None,
                    item.routing_enabled,
                    item.minimum_managers,
                    item.minimum_analysts,
                )
                for item in self.units
            ),
            edges=tuple(
                HierarchyEdgeSpec(
                    item.parent_unit_id,
                    item.child_unit_id,
                    stored_utc(item.effective_from),
                    stored_utc(item.effective_until)
                    if item.effective_until is not None
                    else None,
                )
                for item in self.edges
            ),
            candidate_groups=tuple(
                CandidateGroupSpec(item.unit_id, item.purpose, item.candidate_group)
                for item in self.candidate_groups
            ),
            workflow_template=WorkflowTemplateSpec(
                schema_id=template.schema_id,
                form_version=template.form_version,
                notification_policy_version=template.notification_policy_version,
                organisation_root_id=template.organisation_root_id,
                route_depth=template.route_depth,
                core_fields=tuple(template.core_fields),
                service_categories=tuple(template.service_categories),
                product_types=tuple(template.product_types),
                task_labels=template.task_labels,
                allowed_outcomes={
                    key: tuple(values)
                    for key, values in template.allowed_outcomes.items()
                },
                reminder_days=tuple(template.reminder_days),
                artefact_types=tuple(template.artefact_types),
                approved_link_domains=tuple(template.approved_link_domains),
                workflow_definition_id=template.workflow_definition_id,
            ),
        )


def workflow_specification(
    workflow: ApprovedWorkflowDefinition | None,
) -> ApprovedWorkflowSpec | None:
    if workflow is None:
        return None
    return ApprovedWorkflowSpec(
        id=workflow.id,
        compatibility_key=workflow.compatibility_key,
        available=workflow.is_available,
    )
