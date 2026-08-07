"""Fail-closed operator attestation of an exact Camunda deployment."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_models import ApprovedWorkflowDefinition
from istari_service.operations_models import OperationalRun

ATTESTATION_CONFIRMATION = "ATTEST_WORKFLOW_AVAILABILITY"
ATTESTATION_POLICY_VERSION = "1"


@dataclass(frozen=True, slots=True)
class WorkflowAttestation:
    process_id: str
    process_version: int
    process_definition_key: str
    deployment_key: str
    compatibility_key: str
    checksum: str
    operator_subject: str


async def attest_workflow_availability(
    session: AsyncSession,
    command: WorkflowAttestation,
    *,
    apply: bool,
    confirmation: str | None,
) -> bool:
    """Verify approved identity before recording runtime availability."""

    _validate(command)
    definition = await session.scalar(
        select(ApprovedWorkflowDefinition)
        .where(
            ApprovedWorkflowDefinition.process_id == command.process_id,
            ApprovedWorkflowDefinition.process_version == command.process_version,
        )
        .with_for_update()
    )
    if (
        definition is None
        or definition.checksum != command.checksum.lower()
        or definition.compatibility_key != command.compatibility_key
    ):
        raise ValueError("deployment does not match an approved workflow definition")
    if not apply:
        return True
    if confirmation != ATTESTATION_CONFIRMATION:
        raise ValueError(f"confirmation must equal {ATTESTATION_CONFIRMATION!r}")
    definition.process_definition_key = command.process_definition_key
    definition.deployment_key = command.deployment_key
    definition.is_available = True
    session.add(
        OperationalRun(
            job_name="workflow-availability-attestation",
            policy_version=ATTESTATION_POLICY_VERSION,
            mode="apply",
            criteria={
                "processId": command.process_id,
                "processVersion": command.process_version,
                "processDefinitionKey": command.process_definition_key,
                "deploymentKey": command.deployment_key,
                "compatibilityKey": command.compatibility_key,
                "checksum": command.checksum.lower(),
                "operatorSubjectHash": hashlib.sha256(
                    command.operator_subject.encode("utf-8")
                ).hexdigest(),
            },
            result_counts={"definitionsAttested": 1},
        )
    )
    await session.flush()
    return True


def _validate(command: WorkflowAttestation) -> None:
    values = {
        "process ID": (command.process_id, 160),
        "process definition key": (command.process_definition_key, 128),
        "deployment key": (command.deployment_key, 128),
        "compatibility key": (command.compatibility_key, 80),
        "operator subject": (command.operator_subject, 240),
    }
    for label, (value, maximum) in values.items():
        if not value.strip() or len(value) > maximum:
            raise ValueError(f"{label} is invalid")
    if command.process_version < 1:
        raise ValueError("process version must be positive")
    checksum = command.checksum.lower()
    invalid_digest = any(character not in "0123456789abcdef" for character in checksum)
    if len(checksum) != 64 or invalid_digest:
        raise ValueError("checksum must be a SHA-256 digest")
