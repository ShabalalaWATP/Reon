"""Pure validation entry point for bounded configuration snapshots."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable, Mapping
from datetime import datetime
from uuid import UUID

from mist_service.configuration_hierarchy_validation import validate_hierarchy
from mist_service.configuration_policy import (
    CORE_REQUEST_FIELDS,
    HUMAN_TASK_OUTCOMES,
    ROUTE_DEPTH,
    WORKFLOW_COMPATIBILITY_KEY,
    WORKFLOW_SCHEMA_ID,
)
from mist_service.configuration_types import (
    ApprovedWorkflowSpec,
    ConfigurationDraftSpec,
    FindingSeverity,
    StaffingCount,
    ValidationFinding,
)

DOMAIN_NAME = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def validate_configuration(
    specification: ConfigurationDraftSpec,
    *,
    effective_from: datetime,
    workflow: ApprovedWorkflowSpec | None,
    staffing: Mapping[UUID, StaffingCount],
) -> list[ValidationFinding]:
    findings = _validate_workflow(specification, workflow)
    findings.extend(
        validate_hierarchy(
            specification,
            effective_from=effective_from,
            staffing=staffing,
        )
    )
    return _deduplicate(findings)


def _finding(
    code: str,
    message: str,
    path: str,
) -> ValidationFinding:
    return ValidationFinding(FindingSeverity.ERROR, code, message, path)


def _validate_workflow(
    specification: ConfigurationDraftSpec,
    workflow: ApprovedWorkflowSpec | None,
) -> list[ValidationFinding]:
    template = specification.workflow_template
    errors: list[ValidationFinding] = []
    if template.schema_id != WORKFLOW_SCHEMA_ID:
        errors.append(
            _finding(
                "WORKFLOW_SCHEMA_INVALID",
                "The workflow template schema is not allow-listed.",
                "workflowTemplate.schemaId",
            )
        )
    if set(template.core_fields) != CORE_REQUEST_FIELDS:
        errors.append(
            _finding(
                "CORE_FIELDS_INVALID",
                "Every mandatory request field must remain present and unchanged.",
                "workflowTemplate.coreFields",
            )
        )
    if template.route_depth != ROUTE_DEPTH:
        errors.append(
            _finding(
                "ROUTE_DEPTH_INVALID",
                "The human route must retain three organisation edges.",
                "workflowTemplate.routeDepth",
            )
        )
    expected_tasks = set(HUMAN_TASK_OUTCOMES)
    if set(template.task_labels) != expected_tasks:
        errors.append(
            _finding(
                "HUMAN_TASKS_INVALID",
                "Every required human task must have exactly one bounded label.",
                "workflowTemplate.taskLabels",
            )
        )
    supplied_outcomes = {
        key: frozenset(values) for key, values in template.allowed_outcomes.items()
    }
    if supplied_outcomes != HUMAN_TASK_OUTCOMES:
        errors.append(
            _finding(
                "HUMAN_OUTCOMES_INVALID",
                "Configured outcomes cannot add, remove or bypass a human decision.",
                "workflowTemplate.allowedOutcomes",
            )
        )
    if workflow is None or workflow.id != template.workflow_definition_id:
        errors.append(
            _finding(
                "WORKFLOW_DEFINITION_UNKNOWN",
                "Select an approved deployed workflow definition.",
                "workflowTemplate.workflowDefinitionId",
            )
        )
    elif (
        not workflow.available
        or workflow.compatibility_key != WORKFLOW_COMPATIBILITY_KEY
    ):
        errors.append(
            _finding(
                "WORKFLOW_DEFINITION_INCOMPATIBLE",
                "The deployed workflow is unavailable or incompatible.",
                "workflowTemplate.workflowDefinitionId",
            )
        )
    for index, domain in enumerate(template.approved_link_domains):
        if not _safe_domain(domain):
            errors.append(
                _finding(
                    "LINK_DOMAIN_INVALID",
                    "Approved link entries must be public DNS domain names only.",
                    f"workflowTemplate.approvedLinkDomains.{index}",
                )
            )
    return errors


def _safe_domain(value: str) -> bool:
    if value in {"localhost", "localhost.localdomain"} or not DOMAIN_NAME.fullmatch(
        value
    ):
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return True
    return False


def _deduplicate(findings: Iterable[ValidationFinding]) -> list[ValidationFinding]:
    unique = {
        (item.severity, item.code, item.path, item.unit_id, item.message): item
        for item in findings
    }
    return sorted(
        unique.values(),
        key=lambda item: (
            item.severity.value,
            item.code,
            str(item.unit_id or ""),
            item.path,
        ),
    )
