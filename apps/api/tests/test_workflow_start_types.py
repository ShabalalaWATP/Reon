"""Validation tests for durable workflow-start commands."""

from __future__ import annotations

from uuid import uuid4

import pytest

from istari_service.workflow_start_types import WorkflowStartCommand


def test_workflow_start_command_round_trips_pinned_identity() -> None:
    command = WorkflowStartCommand(
        request_id=uuid4(),
        requester_id=uuid4(),
        process_id="service-request-v1",
        process_version=7,
        process_checksum="a" * 64,
    )

    assert WorkflowStartCommand.from_payload(command.to_payload()) == command


def test_workflow_start_command_accepts_explicit_legacy_process_fallback() -> None:
    request_id = uuid4()
    requester_id = uuid4()

    command = WorkflowStartCommand.from_payload(
        {"requestId": str(request_id), "requesterId": str(requester_id)},
        legacy_process_id="legacy-process",
    )

    assert command.process_id == "legacy-process"
    assert command.to_payload() == {
        "requestId": str(request_id),
        "requesterId": str(requester_id),
        "processId": "legacy-process",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"requestId": 3, "requesterId": str(uuid4()), "processId": "process"},
        {"requestId": "not-a-uuid", "requesterId": str(uuid4())},
        {
            "requestId": str(uuid4()),
            "requesterId": str(uuid4()),
            "processId": " service-request ",
        },
        {
            "requestId": str(uuid4()),
            "requesterId": str(uuid4()),
            "processId": "service-request",
            "processVersion": True,
        },
        {
            "requestId": str(uuid4()),
            "requesterId": str(uuid4()),
            "processId": "service-request",
            "processChecksum": "not-a-checksum",
        },
        {
            "requestId": str(uuid4()),
            "requesterId": str(uuid4()),
            "processId": 7,
        },
        {
            "requestId": str(uuid4()),
            "requesterId": str(uuid4()),
            "processId": "service-request",
            "processChecksum": 7,
        },
    ],
)
def test_workflow_start_command_rejects_malformed_payload(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        WorkflowStartCommand.from_payload(payload)


def test_workflow_start_command_rejects_invalid_direct_version() -> None:
    with pytest.raises(ValueError, match="version"):
        WorkflowStartCommand(uuid4(), uuid4(), "service-request", 0)
