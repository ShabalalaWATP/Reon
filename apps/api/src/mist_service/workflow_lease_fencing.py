"""Shared fencing and backoff rules for the workflow outbox dispatchers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.models import OutboxStatus, WorkflowOutbox

MAXIMUM_RETRY_DELAY_SECONDS = 30


async def lock_leased_outbox(
    session: AsyncSession,
    *,
    outbox_id: UUID,
    lease_owner: str,
    lease_generation: int,
) -> WorkflowOutbox | None:
    """Lock one outbox row only while this worker still holds its exact lease.

    Status, owner and generation together fence the row. A worker whose lease
    was superseded matches nothing and therefore cannot finalise stale work.
    Every dispatcher shares this one definition so the fence cannot drift.
    """

    outbox: WorkflowOutbox | None = await session.scalar(
        select(WorkflowOutbox)
        .where(
            WorkflowOutbox.id == outbox_id,
            WorkflowOutbox.status == OutboxStatus.PROCESSING,
            WorkflowOutbox.lease_owner == lease_owner,
            WorkflowOutbox.lease_generation == lease_generation,
        )
        .with_for_update()
    )
    return outbox


def retry_delay_seconds(attempts: int) -> int:
    """Return the capped exponential backoff shared by every dispatcher."""

    return min(int(2**attempts), MAXIMUM_RETRY_DELAY_SECONDS)
