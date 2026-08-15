"""Focused edge coverage for durable workflow-start leasing."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from conftest import ApiHarness, request_payload
from mist_service.models import OutboxStatus, WorkflowOutbox
from mist_service.workflow_start_lease import claim_pending_start


async def test_invalid_start_command_fails_the_claimed_outbox(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await api_harness.login("admin2")
    response = await api_harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 201

    monkeypatch.setattr(
        "mist_service.workflow_start_lease.reject_invalid_start_identity",
        lambda *_args: False,
    )
    async with api_harness.sessions() as session, session.begin():
        outbox = await session.scalar(select(WorkflowOutbox))
        assert outbox is not None
        outbox.payload = {**outbox.payload, "processVersion": "invalid"}

        pending = await claim_pending_start(
            session,
            legacy_process_id=api_harness.settings.camunda_process_id,
            now=datetime.now(UTC),
        )

        assert pending is None
        assert outbox.status == OutboxStatus.FAILED
        assert outbox.lease_owner is None
        assert outbox.last_error == "Workflow start command is invalid."
