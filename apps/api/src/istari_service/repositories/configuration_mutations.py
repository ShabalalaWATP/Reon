"""Focused SQLAlchemy mutations for configuration components and findings."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_models import (
    ConfigurationCandidateGroup,
    ConfigurationHierarchyEdge,
    ConfigurationUnitRevision,
    ConfigurationValidationFinding,
    ConfigurationWorkflowTemplate,
)
from istari_service.configuration_policy import WORKFLOW_SCHEMA_DIGEST
from istari_service.configuration_types import ConfigurationDraftSpec, ValidationFinding


async def replace_configuration_components(
    session: AsyncSession,
    version_id: UUID,
    specification: ConfigurationDraftSpec,
) -> None:
    """Replace the child rows for an already locked draft version."""

    for model in (
        ConfigurationValidationFinding,
        ConfigurationCandidateGroup,
        ConfigurationHierarchyEdge,
        ConfigurationUnitRevision,
        ConfigurationWorkflowTemplate,
    ):
        await session.execute(
            delete(model).where(model.configuration_version_id == version_id)
        )
    session.add_all(
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
    session.add_all(
        ConfigurationHierarchyEdge(
            configuration_version_id=version_id,
            parent_unit_id=item.parent_unit_id,
            child_unit_id=item.child_unit_id,
            effective_from=item.effective_from,
            effective_until=item.effective_until,
        )
        for item in specification.edges
    )
    session.add_all(
        ConfigurationCandidateGroup(
            configuration_version_id=version_id,
            unit_id=item.unit_id,
            purpose=item.purpose,
            candidate_group=item.candidate_group,
        )
        for item in specification.candidate_groups
    )
    template = specification.workflow_template
    session.add(
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
                key: list(values) for key, values in template.allowed_outcomes.items()
            },
            reminder_days=list(template.reminder_days),
            artefact_types=list(template.artefact_types),
            approved_link_domains=list(template.approved_link_domains),
            workflow_definition_id=template.workflow_definition_id,
        )
    )
    await session.flush()


async def replace_configuration_findings(
    session: AsyncSession,
    version_id: UUID,
    findings: list[ValidationFinding],
) -> None:
    """Replace validation evidence for one mutable candidate version."""

    await session.execute(
        delete(ConfigurationValidationFinding).where(
            ConfigurationValidationFinding.configuration_version_id == version_id
        )
    )
    session.add_all(
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
    await session.flush()
