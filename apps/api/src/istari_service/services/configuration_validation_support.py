"""Shared validated configuration findings for command use cases."""

from __future__ import annotations

from istari_service.configuration_types import ValidationFinding
from istari_service.configuration_validation import validate_configuration
from istari_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from istari_service.repositories.configuration_records import (
    ConfigurationBundle,
    stored_utc,
    workflow_specification,
)
from istari_service.repositories.configuration_staffing import load_staffing_counts


async def configuration_findings(
    repository: SqlAlchemyConfigurationRepository,
    bundle: ConfigurationBundle,
) -> list[ValidationFinding]:
    """Build findings from one repository-owned configuration snapshot."""

    specification = bundle.specification()
    workflow = await repository.approved_workflow(
        specification.workflow_template.workflow_definition_id
    )
    staffing = await load_staffing_counts(
        repository.session,
        {item.unit_id for item in specification.units},
    )
    return validate_configuration(
        specification,
        effective_from=stored_utc(bundle.version.effective_from),
        workflow=workflow_specification(workflow),
        staffing=staffing,
    )
