"""Transactional leasing for durable workflow-start outbox records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.configuration_models import RequestConfigurationPin
from mist_service.models import (
    OutboxStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowOutbox,
)
from mist_service.workflow_lease_fencing import lock_leased_outbox
from mist_service.workflow_start_types import WorkflowStartCommand
from mist_service.workflow_start_validation import reject_invalid_start_identity


@dataclass(frozen=True, slots=True)
class PendingStart:
    outbox_id: UUID
    request_id: UUID
    requester_id: UUID
    attempts: int
    lease_owner: str
    lease_generation: int
    process_id: str = "service-request-v1"
    process_version: int = -1


async def claim_pending_start(
    session: AsyncSession,
    *,
    legacy_process_id: str,
    now: datetime,
    lease_seconds: int = 30,
) -> PendingStart | None:
    """Claim the oldest eligible start command inside the caller transaction."""

    outbox = await session.scalar(
        select(WorkflowOutbox)
        .where(
            WorkflowOutbox.event_type == "START_PROCESS",
            WorkflowOutbox.status.in_([OutboxStatus.PENDING, OutboxStatus.PROCESSING]),
            WorkflowOutbox.available_at <= now,
        )
        .order_by(WorkflowOutbox.created_at, WorkflowOutbox.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if outbox is None:
        return None
    request = await session.get(ServiceRequest, outbox.request_id)
    if request is None:
        outbox.status = OutboxStatus.FAILED
        outbox.lease_owner = None
        outbox.last_error = "Associated request is missing."
        return None
    instance = await session.scalar(
        select(WorkflowInstance).where(WorkflowInstance.request_id == outbox.request_id)
    )
    pin = await session.scalar(
        select(RequestConfigurationPin).where(
            RequestConfigurationPin.request_id == outbox.request_id
        )
    )
    if reject_invalid_start_identity(pin, outbox, request, instance):
        return None
    lease_owner = uuid4().hex
    outbox.status = OutboxStatus.PROCESSING
    outbox.attempts += 1
    outbox.lease_owner = lease_owner
    outbox.lease_generation += 1
    outbox.available_at = now + timedelta(seconds=lease_seconds)
    try:
        command = WorkflowStartCommand.from_payload(
            outbox.payload,
            legacy_process_id=legacy_process_id,
        )
    except ValueError:
        outbox.status = OutboxStatus.FAILED
        outbox.lease_owner = None
        outbox.last_error = "Workflow start command is invalid."
        return None
    return PendingStart(
        outbox_id=outbox.id,
        request_id=request.id,
        requester_id=request.requester_id,
        attempts=outbox.attempts,
        lease_owner=lease_owner,
        lease_generation=outbox.lease_generation,
        process_id=command.process_id,
        process_version=command.process_version or -1,
    )


async def lock_start_lease(
    session: AsyncSession,
    pending: PendingStart,
) -> WorkflowOutbox | None:
    """Lock a current lease so a superseded worker cannot finalise it."""

    return await lock_leased_outbox(
        session,
        outbox_id=pending.outbox_id,
        lease_owner=pending.lease_owner,
        lease_generation=pending.lease_generation,
    )
