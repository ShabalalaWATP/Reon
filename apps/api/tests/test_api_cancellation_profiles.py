"""Requester cancellation behaviour."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from api_helpers import submit_request
from conftest import ApiHarness, request_payload
from istari_service.action_notification_models import NotificationEvent
from istari_service.board_models import (
    CapacityReservation,
    ReservationStatus,
    WorkPackage,
    WorkPackageActivity,
    WorkPackagePriority,
    WorkPackageStatus,
)
from istari_service.clarification_models import (
    ClarificationStatus,
    ClarificationThread,
)
from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound
from istari_service.models import (
    OutboxStatus,
    RequestEvent,
    RequestStatus,
    ServiceRequest,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
    WorkflowTask,
    WorkflowTaskStatus,
)
from istari_service.repositories.request_cancellation import (
    _record_workflow_cancellation,
    cancel_request,
)
from istari_service.schemas.requests import RequestCancel
from istari_service.workflow_cancellation_dispatch import (
    WorkflowCancellationDispatcher,
)


async def test_requester_cancellation_closes_work_and_notifies_route(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = UUID(await submit_request(harness))
    team_id = await harness.unit_id("OSG_TEAM")
    specialist_id = await harness.user_id("admin11")
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        package = WorkPackage(
            team_id=team_id,
            linked_request_id=request_id,
            title="Synthetic linked package",
            description="Synthetic planning description.",
            owner_user_id=specialist_id,
            estimate_points=5,
            remaining_effort_minutes=240,
            due_on=(now + timedelta(days=10)).date(),
            priority=WorkPackagePriority.HIGH,
            status=WorkPackageStatus.IN_PROGRESS,
            blockers="No synthetic blockers.",
            acceptance_criteria="The fictional request is completed.",
            created_by_user_id=specialist_id,
            version=1,
        )
        session.add(package)
        await session.flush()
        session.add(
            CapacityReservation(
                package_id=package.id,
                team_id=team_id,
                user_id=specialist_id,
                starts_at=now,
                ends_at=now + timedelta(hours=2),
                minutes=120,
                status=ReservationStatus.ACTIVE,
                reason="Synthetic capacity reservation.",
                created_by_user_id=specialist_id,
                version=1,
            )
        )
        session.add(
            ClarificationThread(
                request_id=request_id,
                sequence=1,
                requested_by_user_id=specialist_id,
                assigned_specialist_id=specialist_id,
                question="Synthetic defensive clarification.",
                reason="Exercises closure of an inconsistent open thread.",
                response_deadline=(now + timedelta(days=5)).date(),
                status=ClarificationStatus.OPEN,
                version=1,
            )
        )
    before = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert before.status_code == 200

    cancelled = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={
            "expectedVersion": before.json()["version"],
            "reason": "The fictional requirement is no longer needed.",
        },
        headers=harness.mutation_headers(),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["currentOwner"] == "Customer"

    async with harness.sessions() as session:
        task = await session.scalar(
            select(WorkflowTask).where(WorkflowTask.request_id == request_id)
        )
        cancellation = await session.scalar(
            select(WorkflowOutbox).where(
                WorkflowOutbox.request_id == request_id,
                WorkflowOutbox.event_type == "CANCEL_PROCESS",
            )
        )
        event = await session.scalar(
            select(RequestEvent).where(
                RequestEvent.request_id == request_id,
                RequestEvent.type == "request_cancelled",
            )
        )
        notification = await session.scalar(
            select(NotificationEvent).where(
                NotificationEvent.request_id == request_id,
                NotificationEvent.event_type == "REQUEST_CANCELLED",
            )
        )
        package = await session.scalar(
            select(WorkPackage).where(WorkPackage.linked_request_id == request_id)
        )
        assert package is not None
        reservation = await session.scalar(
            select(CapacityReservation).where(
                CapacityReservation.package_id == package.id
            )
        )
        package_activity = await session.scalar(
            select(WorkPackageActivity).where(
                WorkPackageActivity.package_id == package.id
            )
        )
        clarification = await session.scalar(
            select(ClarificationThread).where(
                ClarificationThread.request_id == request_id
            )
        )
        assert task is not None and task.status is WorkflowTaskStatus.CANCELLED
        assert cancellation is not None
        assert cancellation.status is OutboxStatus.PENDING
        assert event is not None
        assert event.details == {
            "reason": "The fictional requirement is no longer needed."
        }
        assert notification is not None
        assert package.status is WorkPackageStatus.CANCELLED
        assert reservation is not None
        assert reservation.status is ReservationStatus.CANCELLED
        assert reservation.cancellation_reason == (
            "The fictional requirement is no longer needed."
        )
        assert package_activity is not None
        assert clarification is not None
        assert clarification.status is ClarificationStatus.WITHDRAWN
        recipient_ids = {rule["userId"] for rule in notification.audience}
        assert str(await harness.user_id("admin2")) in recipient_ids
        assert str(await harness.user_id("admin4")) in recipient_ids

    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        await _record_workflow_cancellation(session, request, datetime.now(UTC))
        cancellations = list(
            await session.scalars(
                select(WorkflowOutbox).where(
                    WorkflowOutbox.request_id == request_id,
                    WorkflowOutbox.event_type == "CANCEL_PROCESS",
                )
            )
        )
        assert len(cancellations) == 1

    dispatcher = WorkflowCancellationDispatcher(harness.sessions, harness.workflow)
    assert await dispatcher.dispatch_once()
    assert not await dispatcher.dispatch_once()
    assert len(harness.workflow.cancellation_commands) == 1
    assert harness.workflow.active_tasks == ()
    async with harness.sessions() as session:
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        assert instance is not None
        assert instance.status is WorkflowInstanceStatus.TERMINATED


async def test_cancellation_is_owner_only_versioned_and_non_repeatable(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = UUID(await submit_request(harness))
    await harness.login("admin3")
    forbidden = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={"expectedVersion": 1, "reason": "This must not be authorised."},
        headers=harness.mutation_headers(),
    )
    assert forbidden.status_code == 404

    await harness.login("admin2")
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    version = detail.json()["version"]
    stale = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={"expectedVersion": version - 1, "reason": "A stale cancellation."},
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409
    short = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={"expectedVersion": version, "reason": "Too short"},
        headers=harness.mutation_headers(),
    )
    assert short.status_code == 422
    unsafe = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={
            "expectedVersion": version,
            "reason": "Unsafe cancellation\u202e reason.",
        },
        headers=harness.mutation_headers(),
    )
    assert unsafe.status_code == 422
    accepted = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={"expectedVersion": version, "reason": "Requirement withdrawn."},
        headers=harness.mutation_headers(),
    )
    assert accepted.status_code == 200
    repeated = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={
            "expectedVersion": accepted.json()["version"],
            "reason": "Trying to cancel a closed request.",
        },
        headers=harness.mutation_headers(),
    )
    assert repeated.status_code == 409

    actor = Actor(
        id=await harness.user_id("admin2"),
        username="admin2",
        display_name="John McGinn",
        role=UserRole.REQUESTER,
        scope="Customer",
    )
    async with harness.sessions() as session:
        with pytest.raises(ObjectNotFound):
            await cancel_request(
                session,
                uuid4(),
                actor,
                RequestCancel(expected_version=1, reason="A missing request reason."),
            )


async def test_cancel_before_workflow_start_suppresses_the_start(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    created = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    request_id = UUID(created.json()["id"])
    cancelled = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={
            "expectedVersion": created.json()["version"],
            "reason": "Cancelled before the workflow started.",
        },
        headers=harness.mutation_headers(),
    )
    assert cancelled.status_code == 200
    assert not await harness.dispatch_start()
    assert harness.workflow.start_commands == ()
    async with harness.sessions() as session:
        request = await session.get(ServiceRequest, request_id)
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        outboxes = list(
            await session.scalars(
                select(WorkflowOutbox).where(WorkflowOutbox.request_id == request_id)
            )
        )
        assert request is not None and request.status is RequestStatus.CANCELLED
        assert instance is not None
        assert instance.status is WorkflowInstanceStatus.TERMINATED
        assert [outbox.event_type for outbox in outboxes] == ["START_PROCESS"]
        assert outboxes[0].status is OutboxStatus.SENT


async def test_missing_workflow_instance_fails_cancellation_atomically(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = UUID(await submit_request(harness))
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    async with harness.sessions() as session, session.begin():
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        assert instance is not None
        await session.delete(instance)

    response = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={
            "expectedVersion": detail.json()["version"],
            "reason": "This cancellation must roll back safely.",
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 409
    async with harness.sessions() as session:
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        assert request.status is RequestStatus.TRIAGE_REVIEW
