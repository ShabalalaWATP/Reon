"""Operator workflow deployment attestation contracts."""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import select

from conftest import ApiHarness
from mist_service.configuration_models import ApprovedWorkflowDefinition
from mist_service.configuration_policy import WORKFLOW_COMPATIBILITY_KEY
from mist_service.operations_models import OperationalRun
from mist_service.workflow_attestation import (
    ATTESTATION_CONFIRMATION,
    WorkflowAttestation,
    attest_workflow_availability,
)


def _command(
    checksum: str, *, operator: str = "ops:test-operator"
) -> WorkflowAttestation:
    return WorkflowAttestation(
        process_id="service-request-v1",
        process_version=1,
        process_definition_key="2251799813689999",
        deployment_key="2251799813689998",
        compatibility_key=WORKFLOW_COMPATIBILITY_KEY,
        checksum=checksum,
        operator_subject=operator,
    )


async def test_exact_deployment_attestation_records_operator_evidence(
    api_harness: ApiHarness,
) -> None:
    async with api_harness.sessions() as session, session.begin():
        definition = await session.scalar(select(ApprovedWorkflowDefinition))
        assert definition is not None
        definition.is_available = False
        command = _command(definition.checksum)
        assert await attest_workflow_availability(
            session,
            command,
            apply=False,
            confirmation=None,
        )
        assert definition.is_available is False
        assert await attest_workflow_availability(
            session,
            command,
            apply=True,
            confirmation=ATTESTATION_CONFIRMATION,
        )
        assert definition.is_available is True
        assert definition.process_definition_key == command.process_definition_key
        evidence = await session.scalar(
            select(OperationalRun).where(
                OperationalRun.job_name == "workflow-availability-attestation"
            )
        )
        assert evidence is not None
        assert (
            evidence.criteria["operatorSubjectHash"]
            == hashlib.sha256(command.operator_subject.encode("utf-8")).hexdigest()
        )


async def test_attestation_rejects_mismatch_and_missing_confirmation(
    api_harness: ApiHarness,
) -> None:
    async with api_harness.sessions() as session, session.begin():
        definition = await session.scalar(select(ApprovedWorkflowDefinition))
        assert definition is not None
        with pytest.raises(ValueError, match="approved workflow"):
            await attest_workflow_availability(
                session,
                _command("0" * 64),
                apply=False,
                confirmation=None,
            )
        with pytest.raises(ValueError, match="confirmation"):
            await attest_workflow_availability(
                session,
                _command(definition.checksum),
                apply=True,
                confirmation="wrong",
            )


@pytest.mark.parametrize(
    "command",
    [
        _command("x" * 64),
        _command("0" * 64, operator=""),
        WorkflowAttestation("", 0, "", "", "", "0", ""),
    ],
)
async def test_attestation_validates_bounded_identity(
    api_harness: ApiHarness,
    command: WorkflowAttestation,
) -> None:
    async with api_harness.sessions() as session:
        with pytest.raises(ValueError):
            await attest_workflow_availability(
                session,
                command,
                apply=False,
                confirmation=None,
            )
