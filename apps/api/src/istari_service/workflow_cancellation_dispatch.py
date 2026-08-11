"""Fenced dispatch of durable process-cancellation commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.models import (
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
)
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow.errors import (
    WorkflowConflict,
    WorkflowError,
    WorkflowTaskNotFound,
)
from istari_service.workflow.types import (
    CancelProcessCommand,
    ProcessStateQuery,
    WorkflowProcessState,
)

CANCELLATION_RETRY = "Workflow cancellation will be retried."
CANCELLATION_SUPPORT = "Workflow cancellation needs support."


@dataclass(frozen=True, slots=True)
class PendingCancellation:
    outbox_id: UUID
    request_id: UUID
    process_instance_key: str
    attempts: int
    lease_owner: str
    lease_generation: int


class WorkflowCancellationDispatcher:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        engine: WorkflowEngine,
        *,
        max_attempts: int = 30,
        lease_seconds: int = 30,
    ) -> None:
        self._sessions = sessions
        self._engine = engine
        self._max_attempts = max_attempts
        self._lease_seconds = lease_seconds

    async def dispatch_once(self) -> bool:
        pending, handled = await self._claim_next()
        if pending is None:
            return handled
        try:
            await self._cancel_idempotently(pending)
        except WorkflowError:
            await self._record_retry(pending)
        else:
            await self._record_success(pending)
        return True

    async def _claim_next(self) -> tuple[PendingCancellation | None, bool]:
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            outbox = await session.scalar(
                select(WorkflowOutbox)
                .where(
                    WorkflowOutbox.event_type == "CANCEL_PROCESS",
                    WorkflowOutbox.status.in_(
                        [OutboxStatus.PENDING, OutboxStatus.PROCESSING]
                    ),
                    WorkflowOutbox.available_at <= now,
                )
                .order_by(WorkflowOutbox.created_at, WorkflowOutbox.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if outbox is None:
                return None, False
            request = await session.get(ServiceRequest, outbox.request_id)
            instance = await session.scalar(
                select(WorkflowInstance)
                .where(WorkflowInstance.request_id == outbox.request_id)
                .with_for_update()
            )
            if request is None or instance is None:
                outbox.status = OutboxStatus.FAILED
                outbox.lease_owner = None
                outbox.last_error = CANCELLATION_SUPPORT
                return None, True
            if request.status is not RequestStatus.CANCELLED:
                outbox.status = OutboxStatus.FAILED
                outbox.lease_owner = None
                outbox.last_error = CANCELLATION_SUPPORT
                return None, True
            if instance.status is WorkflowInstanceStatus.TERMINATED:
                self._mark_sent(outbox, now)
                return None, True
            if not instance.process_instance_key:
                outbox.attempts += 1
                exhausted = outbox.attempts >= self._max_attempts
                outbox.status = (
                    OutboxStatus.FAILED if exhausted else OutboxStatus.PENDING
                )
                outbox.lease_owner = None
                outbox.last_error = (
                    CANCELLATION_SUPPORT if exhausted else CANCELLATION_RETRY
                )
                retry_delay = min(2**outbox.attempts, 30)
                outbox.available_at = now + timedelta(seconds=retry_delay)
                if exhausted:
                    request.workflow_error = CANCELLATION_SUPPORT
                    instance.last_error = CANCELLATION_SUPPORT
                return None, True
            owner = uuid4().hex
            outbox.status = OutboxStatus.PROCESSING
            outbox.attempts += 1
            outbox.lease_owner = owner
            outbox.lease_generation += 1
            outbox.available_at = now + timedelta(seconds=self._lease_seconds)
            return PendingCancellation(
                outbox.id,
                request.id,
                instance.process_instance_key,
                outbox.attempts,
                owner,
                outbox.lease_generation,
            ), True

    async def _cancel_idempotently(self, pending: PendingCancellation) -> None:
        try:
            await self._engine.cancel_process(
                CancelProcessCommand(pending.process_instance_key)
            )
            return
        except (WorkflowConflict, WorkflowTaskNotFound) as error:
            state = await self._engine.find_process_state(
                ProcessStateQuery(pending.process_instance_key)
            )
            if state is not None and state.state is WorkflowProcessState.TERMINATED:
                return
            raise error

    async def _record_success(self, pending: PendingCancellation) -> None:
        async with self._sessions() as session, session.begin():
            outbox = await self._lock_lease(session, pending)
            if outbox is None:
                return
            request = await session.get(ServiceRequest, pending.request_id)
            instance = await session.scalar(
                select(WorkflowInstance)
                .where(WorkflowInstance.request_id == pending.request_id)
                .with_for_update()
            )
            now = datetime.now(UTC)
            if instance is not None:
                instance.status = WorkflowInstanceStatus.TERMINATED
                instance.current_element_id = None
                instance.completed_at = now
                instance.last_error = None
            if request is not None:
                request.workflow_error = None
            self._mark_sent(outbox, now)

    async def _record_retry(self, pending: PendingCancellation) -> None:
        async with self._sessions() as session, session.begin():
            outbox = await self._lock_lease(session, pending)
            if outbox is None:
                return
            exhausted = pending.attempts >= self._max_attempts
            outbox.status = OutboxStatus.FAILED if exhausted else OutboxStatus.PENDING
            outbox.lease_owner = None
            outbox.last_error = (
                CANCELLATION_SUPPORT if exhausted else CANCELLATION_RETRY
            )
            outbox.available_at = datetime.now(UTC) + timedelta(
                seconds=min(2**pending.attempts, 30)
            )
            if exhausted:
                request = await session.get(ServiceRequest, pending.request_id)
                instance = await session.scalar(
                    select(WorkflowInstance).where(
                        WorkflowInstance.request_id == pending.request_id
                    )
                )
                if request is not None:
                    request.workflow_error = CANCELLATION_SUPPORT
                if instance is not None:
                    instance.last_error = CANCELLATION_SUPPORT

    @staticmethod
    async def _lock_lease(
        session: AsyncSession,
        pending: PendingCancellation,
    ) -> WorkflowOutbox | None:
        outbox: WorkflowOutbox | None = await session.scalar(
            select(WorkflowOutbox)
            .where(
                WorkflowOutbox.id == pending.outbox_id,
                WorkflowOutbox.status == OutboxStatus.PROCESSING,
                WorkflowOutbox.lease_owner == pending.lease_owner,
                WorkflowOutbox.lease_generation == pending.lease_generation,
            )
            .with_for_update()
        )
        return outbox

    @staticmethod
    def _mark_sent(outbox: WorkflowOutbox, now: datetime) -> None:
        outbox.status = OutboxStatus.SENT
        outbox.lease_owner = None
        outbox.sent_at = now
        outbox.last_error = None
