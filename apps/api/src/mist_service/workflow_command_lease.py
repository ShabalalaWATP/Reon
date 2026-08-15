"""Lease acquisition, fencing and database recovery for workflow commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import Actor, WorkRecord
from mist_service.errors import InvalidAction
from mist_service.models import OutboxStatus, WorkflowOutbox
from mist_service.work_command_types import (
    PendingWorkCommand,
    WorkCommandType,
    parse_command,
)
from mist_service.workflow.errors import WorkflowError, WorkflowRequestRejected
from mist_service.workflow_command_results import (
    mark_support_failure,
    stored_work_id,
)
from mist_service.workflow_command_state import validated_command_state
from mist_service.workflow_lease_fencing import lock_leased_outbox

COMMAND_TYPES = tuple(command.value for command in WorkCommandType)


@dataclass(frozen=True, slots=True)
class LeasedCommand:
    request_id: UUID
    lease_owner: str
    lease_generation: int
    command: PendingWorkCommand
    actor: Actor
    work: WorkRecord


async def claim_workflow_command(
    session: AsyncSession,
    *,
    outbox_id: UUID | None,
    now: datetime,
    lease_seconds: int,
    managed_products_enabled: bool,
) -> tuple[LeasedCommand | None, WorkflowError | None]:
    """Claim and validate the next command inside the caller transaction."""

    query = (
        select(WorkflowOutbox)
        .where(
            WorkflowOutbox.event_type.in_(COMMAND_TYPES),
            or_(
                WorkflowOutbox.status == OutboxStatus.PENDING,
                WorkflowOutbox.status == OutboxStatus.PROCESSING,
            ),
        )
        .order_by(WorkflowOutbox.created_at, WorkflowOutbox.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if outbox_id is None:
        query = query.where(WorkflowOutbox.available_at <= now)
    else:
        query = query.where(
            WorkflowOutbox.id == outbox_id,
            or_(
                WorkflowOutbox.available_at <= now,
                and_(
                    WorkflowOutbox.status == OutboxStatus.PENDING,
                    WorkflowOutbox.attempts == 0,
                ),
            ),
        )
    outbox = await session.scalar(query)
    if outbox is None:
        return None, None
    owner = uuid4().hex
    outbox.status = OutboxStatus.PROCESSING
    outbox.attempts += 1
    outbox.lease_owner = owner
    outbox.lease_generation += 1
    outbox.available_at = now + timedelta(seconds=lease_seconds)
    try:
        command = parse_command(
            outbox.id,
            outbox.event_type,
            outbox.payload,
            outbox.attempts,
        )
        actor, work = await validated_command_state(
            session,
            command,
            outbox.request_id,
            managed_products_enabled=managed_products_enabled,
        )
    except (InvalidAction, KeyError, TypeError, ValueError, ValidationError):
        await mark_support_failure(
            session,
            outbox,
            stored_work_id(outbox.payload),
        )
        return None, WorkflowRequestRejected("dispatch_workflow_command", 409)
    return (
        LeasedCommand(
            request_id=outbox.request_id,
            lease_owner=owner,
            lease_generation=outbox.lease_generation,
            command=command,
            actor=actor,
            work=work,
        ),
        None,
    )


async def lock_command_lease(
    session: AsyncSession,
    lease: LeasedCommand,
) -> WorkflowOutbox | None:
    """Lock the exact command lease generation held by this worker."""

    return await lock_leased_outbox(
        session,
        outbox_id=lease.command.outbox_id,
        lease_owner=lease.lease_owner,
        lease_generation=lease.lease_generation,
    )


def is_deadlock(error: BaseException) -> bool:
    """Detect PostgreSQL deadlocks through DBAPI wrapper chains."""

    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if (
            getattr(current, "sqlstate", None) == "40P01"
            or getattr(current, "pgcode", None) == "40P01"
        ):
            return True
        for candidate in (
            getattr(current, "orig", None),
            current.__cause__,
            current.__context__,
        ):
            if isinstance(candidate, BaseException):
                pending.append(candidate)
    return False
