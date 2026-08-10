"""Atomic requester cancellation and local work closure."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.board_models import (
    CapacityReservation,
    ReservationStatus,
    WorkPackage,
    WorkPackageActivity,
    WorkPackageActivityType,
    WorkPackageStatus,
)
from istari_service.clarification_models import ClarificationStatus, ClarificationThread
from istari_service.domain import Actor
from istari_service.errors import InvalidAction, ObjectNotFound, StaleVersion
from istari_service.models import (
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
    WorkflowTask,
    WorkflowTaskStatus,
)
from istari_service.ownership import OWNER_BY_STATUS
from istari_service.repositories.clarifications import withdraw_open_clarification
from istari_service.repositories.event_store import append_request_event
from istari_service.repositories.request_views import build_request_detail
from istari_service.schemas.requests import RequestCancel, RequestDetail

TERMINAL_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED,
    RequestStatus.CANCELLED,
}
OPEN_TASK_STATUSES = {
    WorkflowTaskStatus.OPEN,
    WorkflowTaskStatus.CLAIM_PENDING,
    WorkflowTaskStatus.CLAIMED,
    WorkflowTaskStatus.COMPLETION_PENDING,
    WorkflowTaskStatus.ERROR,
}
OPEN_PACKAGE_STATUSES = {
    WorkPackageStatus.BACKLOG,
    WorkPackageStatus.READY,
    WorkPackageStatus.IN_PROGRESS,
    WorkPackageStatus.BLOCKED,
}


async def cancel_request(
    session: AsyncSession,
    request_id: UUID,
    actor: Actor,
    command: RequestCancel,
) -> RequestDetail:
    request = await session.scalar(
        select(ServiceRequest)
        .where(ServiceRequest.id == request_id, ServiceRequest.requester_id == actor.id)
        .with_for_update()
    )
    if request is None:
        raise ObjectNotFound()
    if request.version != command.expected_version:
        raise StaleVersion()
    if request.status in TERMINAL_STATUSES:
        raise InvalidAction("A completed or cancelled request cannot be cancelled.")

    prior_status = request.status
    now = datetime.now(UTC)
    if prior_status is RequestStatus.CUSTOMER_INFORMATION_REQUIRED:
        await withdraw_open_clarification(session, request, actor, command.reason)
    else:
        await _withdraw_unexpected_open_clarification(session, request.id, now)
    await _close_local_work(session, request.id, actor.id, command.reason, now)
    await _record_workflow_cancellation(session, request, now)

    request.status = RequestStatus.CANCELLED
    request.current_owner = OWNER_BY_STATUS[RequestStatus.CANCELLED]
    request.version += 1
    request.workflow_error = None
    await append_request_event(
        session,
        request_id=request.id,
        actor_id=actor.id,
        event_type="request_cancelled",
        message=f"Customer cancelled the request. Reason: {command.reason}",
        prior_status=prior_status,
        next_status=RequestStatus.CANCELLED,
        details={"reason": command.reason},
    )
    await session.flush()
    return await build_request_detail(
        session,
        request.id,
        reveal_unreleased_deliverable=False,
        include_clarifications=True,
    )


async def _close_local_work(
    session: AsyncSession,
    request_id: UUID,
    actor_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    tasks = list(
        await session.scalars(
            select(WorkflowTask)
            .where(
                WorkflowTask.request_id == request_id,
                WorkflowTask.status.in_(OPEN_TASK_STATUSES),
            )
            .with_for_update()
        )
    )
    for task in tasks:
        task.status = WorkflowTaskStatus.CANCELLED
        task.completed_at = now

    packages = list(
        await session.scalars(
            select(WorkPackage)
            .where(
                WorkPackage.linked_request_id == request_id,
                WorkPackage.status.in_(OPEN_PACKAGE_STATUSES),
            )
            .with_for_update()
        )
    )
    package_ids = [package.id for package in packages]
    for package in packages:
        package.status = WorkPackageStatus.CANCELLED
        package.version += 1
        session.add(
            WorkPackageActivity(
                package_id=package.id,
                team_id=package.team_id,
                actor_user_id=actor_id,
                type=WorkPackageActivityType.UPDATED,
                summary="Linked request cancelled by the Customer.",
                details={"requestCancellation": True},
            )
        )
    if not package_ids:
        return
    reservations = list(
        await session.scalars(
            select(CapacityReservation)
            .where(
                CapacityReservation.package_id.in_(package_ids),
                CapacityReservation.status == ReservationStatus.ACTIVE,
            )
            .with_for_update()
        )
    )
    for reservation in reservations:
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_by_user_id = actor_id
        reservation.cancellation_reason = reason
        reservation.version += 1


async def _record_workflow_cancellation(
    session: AsyncSession,
    request: ServiceRequest,
    now: datetime,
) -> None:
    instance = await session.scalar(
        select(WorkflowInstance)
        .where(WorkflowInstance.request_id == request.id)
        .with_for_update()
    )
    if instance is None:
        raise InvalidAction("The request workflow record is unavailable.")
    start = await session.scalar(
        select(WorkflowOutbox)
        .where(
            WorkflowOutbox.request_id == request.id,
            WorkflowOutbox.event_type == "START_PROCESS",
        )
        .with_for_update()
    )
    if (
        instance.process_instance_key is None
        and start is not None
        and start.status
        in {
            OutboxStatus.PENDING,
            OutboxStatus.FAILED,
        }
    ):
        start.status = OutboxStatus.SENT
        start.lease_owner = None
        start.sent_at = now
        start.last_error = None
        instance.status = WorkflowInstanceStatus.TERMINATED
        instance.current_element_id = None
        instance.completed_at = now
        instance.last_error = None
        return
    existing = await session.scalar(
        select(WorkflowOutbox.id).where(
            WorkflowOutbox.idempotency_key == f"cancel:{request.id}"
        )
    )
    if existing is None:
        session.add(
            WorkflowOutbox(
                request_id=request.id,
                event_type="CANCEL_PROCESS",
                payload={"requestId": str(request.id)},
                idempotency_key=f"cancel:{request.id}",
                status=OutboxStatus.PENDING,
                available_at=now,
            )
        )


async def _withdraw_unexpected_open_clarification(
    session: AsyncSession,
    request_id: UUID,
    now: datetime,
) -> None:
    thread = await session.scalar(
        select(ClarificationThread)
        .where(
            ClarificationThread.request_id == request_id,
            ClarificationThread.status == ClarificationStatus.OPEN,
        )
        .with_for_update()
    )
    if thread is not None:
        thread.status = ClarificationStatus.WITHDRAWN
        thread.version += 1
        thread.closed_at = now
