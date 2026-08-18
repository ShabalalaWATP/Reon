"""Pinned configuration identity at request workflow start boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select

from configuration_support import (
    activate_second_configuration,
    seed_configuration_context,
)
from conftest import ApiHarness, request_payload
from mist_service.configuration_models import (
    ApprovedWorkflowDefinition,
    RequestConfigurationPin,
)
from mist_service.models import (
    OutboxStatus,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
)
from mist_service.workflow.lookup import TaskLookupPolicy
from mist_service.workflow_dispatch import WorkflowOutboxDispatcher
from workflow_test_support import FakeWorkflowEngine


async def test_direct_and_draft_requests_dispatch_the_pinned_workflow(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    async with harness.sessions() as session, session.begin():
        actors = await seed_configuration_context(
            session,
            baseline_already_seeded=True,
        )
        activated = await activate_second_configuration(
            session,
            harness.settings,
            actors,
            effective_from=datetime.now(UTC) - timedelta(seconds=1),
        )

    await harness.login("admin2")
    direct = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert direct.status_code == 201, direct.text
    draft = await harness.client.post(
        "/api/v1/request-drafts",
        json={"title": "Pinned workflow draft"},
        headers=harness.mutation_headers(),
    )
    assert draft.status_code == 201, draft.text
    submitted = await harness.client.post(
        f"/api/v1/request-drafts/{draft.json()['id']}/submit",
        json={**request_payload(), "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert submitted.status_code == 200, submitted.text
    request_ids = (UUID(direct.json()["id"]), UUID(submitted.json()["id"]))

    async with harness.sessions() as session:
        for request_id in request_ids:
            pin = await session.scalar(
                select(RequestConfigurationPin).where(
                    RequestConfigurationPin.request_id == request_id
                )
            )
            outbox = await session.scalar(
                select(WorkflowOutbox).where(WorkflowOutbox.request_id == request_id)
            )
            instance = await session.scalar(
                select(WorkflowInstance).where(
                    WorkflowInstance.request_id == request_id
                )
            )
            assert pin is not None and pin.configuration_version_id == activated.id
            assert outbox is not None and instance is not None
            assert outbox.event_type == "START_PROCESS"
            assert (
                pin.snapshot["processId"]
                == outbox.payload["processId"]
                == instance.process_id
                == "service-request-v2"
            )
            assert (
                pin.snapshot["processVersion"]
                == outbox.payload["processVersion"]
                == instance.process_version
                == 2
            )
            assert (
                pin.snapshot["processChecksum"]
                == outbox.payload["processChecksum"]
                == instance.process_checksum
                == "a" * 64
            )

    workflow = FakeWorkflowEngine()
    dispatcher = _dispatcher(harness, workflow, process_id="legacy-fallback")
    assert await dispatcher.dispatch_once()
    assert await dispatcher.dispatch_once()
    assert [
        (item.process_definition_id, item.process_definition_version)
        for item in workflow.start_commands
    ] == [
        ("service-request-v2", 2),
        ("service-request-v2", 2),
    ]


async def test_disabled_admin_surface_still_pins_workflow_identity(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    harness.settings.configuration_admin_enabled = False
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201, response.text
    request_id = UUID(response.json()["id"])
    async with harness.sessions() as session, session.begin():
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.request_id == request_id)
        )
        assert outbox is not None
        pin = await session.scalar(
            select(RequestConfigurationPin).where(
                RequestConfigurationPin.request_id == request_id
            )
        )
        assert pin is not None
        assert outbox.payload["processId"] == pin.snapshot["processId"]
        assert outbox.payload["processVersion"] == pin.snapshot["processVersion"]

    workflow = FakeWorkflowEngine()
    dispatcher = _dispatcher(harness, workflow, process_id="legacy-fallback")
    assert await dispatcher.dispatch_once()
    command = workflow.start_commands[0]
    assert command.process_definition_id == harness.settings.camunda_process_id
    assert command.process_definition_version == 1
    ready = await harness.client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["configuration"] == "ok"


async def test_enabled_configuration_readiness_fails_when_workflow_is_unavailable(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    ready = await harness.client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["configuration"] == "ok"

    async with harness.sessions() as session, session.begin():
        workflow_definition = await session.scalar(
            select(ApprovedWorkflowDefinition).where(
                ApprovedWorkflowDefinition.process_id
                == harness.settings.camunda_process_id
            )
        )
        assert workflow_definition is not None
        workflow_definition.is_available = False

    unavailable = await harness.client.get("/ready")
    assert unavailable.status_code == 503
    assert unavailable.json()["checks"]["configuration"] == "unavailable"


async def test_pinned_start_identity_tamper_fails_without_engine_io(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201, response.text
    request_id = UUID(response.json()["id"])
    async with harness.sessions() as session, session.begin():
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.request_id == request_id)
        )
        assert outbox is not None
        outbox.payload = {**outbox.payload, "processVersion": 999}

    workflow = FakeWorkflowEngine()
    dispatcher = _dispatcher(harness, workflow, process_id="legacy-fallback")
    assert not await dispatcher.dispatch_once()
    assert workflow.start_commands == ()
    async with harness.sessions() as session:
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.request_id == request_id)
        )
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        assert outbox is not None and instance is not None
        assert outbox.status is OutboxStatus.FAILED
        assert instance.status is WorkflowInstanceStatus.ERROR
        assert "does not match" in (outbox.last_error or "")


async def test_unpinned_start_requires_immutable_legacy_marker(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201, response.text
    request_id = UUID(response.json()["id"])
    async with harness.sessions() as session, session.begin():
        await session.execute(
            delete(RequestConfigurationPin).where(
                RequestConfigurationPin.request_id == request_id
            )
        )

    workflow = FakeWorkflowEngine()
    dispatcher = _dispatcher(harness, workflow, process_id="legacy-fallback")
    assert not await dispatcher.dispatch_once()
    assert workflow.start_commands == ()

    async with harness.sessions() as session, session.begin():
        outbox = await session.scalar(
            select(WorkflowOutbox).where(WorkflowOutbox.request_id == request_id)
        )
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        assert outbox is not None and instance is not None
        outbox.status = OutboxStatus.PENDING
        outbox.last_error = None
        outbox.payload = {
            "requestId": str(request_id),
            "requesterId": outbox.payload["requesterId"],
        }
        instance.status = WorkflowInstanceStatus.START_PENDING
        instance.last_error = None
        instance.legacy_unpinned_identity = True

    assert await dispatcher.dispatch_once()
    assert workflow.start_commands[0].process_definition_id == "legacy-fallback"
    assert workflow.start_commands[0].process_definition_version == -1


def _dispatcher(
    harness: ApiHarness,
    workflow: FakeWorkflowEngine,
    *,
    process_id: str,
) -> WorkflowOutboxDispatcher:
    return WorkflowOutboxDispatcher(
        harness.sessions,
        workflow,
        process_id=process_id,
        lookup_policy=TaskLookupPolicy(
            max_attempts=1,
            initial_delay_seconds=0,
            backoff_multiplier=1,
            maximum_delay_seconds=0,
        ),
    )
