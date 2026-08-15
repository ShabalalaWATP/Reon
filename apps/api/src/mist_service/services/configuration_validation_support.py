"""Shared validated configuration findings for command use cases."""

from __future__ import annotations

from mist_service.configuration_records import (
    ApprovedWorkflowRecord,
    ConfigurationBundleRecord,
    stored_utc,
)
from mist_service.configuration_types import ApprovedWorkflowSpec, ValidationFinding
from mist_service.configuration_validation import validate_configuration
from mist_service.services.configuration_ports import ConfigurationValidationPort


def _workflow_specification(
    workflow: ApprovedWorkflowRecord | None,
) -> ApprovedWorkflowSpec | None:
    if workflow is None:
        return None
    return ApprovedWorkflowSpec(
        id=workflow.id,
        compatibility_key=workflow.compatibility_key,
        available=workflow.is_available,
    )


async def configuration_findings(
    repository: ConfigurationValidationPort,
    bundle: ConfigurationBundleRecord,
) -> list[ValidationFinding]:
    """Build findings from one repository-owned configuration snapshot."""

    specification = bundle.specification()
    workflow = await repository.approved_workflow(
        specification.workflow_template.workflow_definition_id
    )
    staffing = await repository.staffing_counts(
        {item.unit_id for item in specification.units}
    )
    return validate_configuration(
        specification,
        effective_from=stored_utc(bundle.version.effective_from),
        workflow=_workflow_specification(workflow),
        staffing=staffing,
    )
