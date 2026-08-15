"""Fenced dispatch and recovery of durable human workflow commands."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.errors import InvalidAction
from mist_service.models import OutboxStatus, WorkflowOutbox
from mist_service.repositories.work import SqlAlchemyWorkRepository
from mist_service.workflow.engine import WorkflowEngine
from mist_service.workflow.errors import (
    WorkflowEngineUnavailable,
    WorkflowError,
    WorkflowRequestRejected,
)
from mist_service.workflow.lookup import TaskLookupPolicy
from mist_service.workflow_command_execution import (
    ClaimSucceeded,
    CommandOutcome,
    CommandRetry,
    CompetingClaim,
    CompletionSucceeded,
    WorkflowCommandExecutor,
)
from mist_service.workflow_command_lease import (
    LeasedCommand,
    claim_workflow_command,
    is_deadlock,
    lock_command_lease,
)
from mist_service.workflow_command_results import (
    mark_sent,
    mark_support_failure,
    project_competing_claim,
    schedule_retry,
)
from mist_service.workflow_command_state import validated_command_state

DEFAULT_COMMAND_LOOKUP = TaskLookupPolicy()


class WorkflowCommandDispatcher:
    """Commit a lease, perform Camunda I/O, then fence the projection."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        engine: WorkflowEngine,
        *,
        lookup_policy: TaskLookupPolicy = DEFAULT_COMMAND_LOOKUP,
        max_attempts: int = 30,
        lease_seconds: int = 30,
        managed_products_enabled: bool = False,
        handoff_poll_attempts: int = 50,
        handoff_poll_seconds: float = 0.02,
        database_retry_attempts: int = 2,
    ) -> None:
        self._sessions = session_factory
        self._executor = WorkflowCommandExecutor(engine, lookup_policy)
        self._max_attempts = max_attempts
        self._lease_seconds = lease_seconds
        self._managed_products_enabled = managed_products_enabled
        self._handoff_poll_attempts = max(1, handoff_poll_attempts)
        self._handoff_poll_seconds = max(0, handoff_poll_seconds)
        self._database_retry_attempts = max(1, database_retry_attempts)

    async def dispatch(self, outbox_id: UUID) -> bool:
        for attempt in range(self._database_retry_attempts):
            try:
                return await self._dispatch_attempt(outbox_id)
            except DBAPIError as error:
                if not is_deadlock(error):
                    raise
                if attempt + 1 >= self._database_retry_attempts:
                    raise WorkflowEngineUnavailable(
                        "workflow command projection deadlocked"
                    ) from error
                await asyncio.sleep(0)
        raise WorkflowEngineUnavailable("workflow command projection unavailable")

    async def _dispatch_attempt(self, outbox_id: UUID) -> bool:
        processed, error = await self._run(outbox_id)
        if error is not None:
            raise error
        if processed:
            return True
        return await self._await_competing_dispatch(outbox_id)

    async def dispatch_once(self) -> bool:
        processed, _error = await self._run(None)
        return processed

    async def _run(self, outbox_id: UUID | None) -> tuple[bool, WorkflowError | None]:
        lease, rejected = await self._claim(outbox_id)
        if rejected is not None:
            return True, rejected
        if lease is None:
            return False, None
        try:
            outcome = await self._executor.execute(lease.command, lease.actor)
            return True, await self._finalise(lease, outcome)
        except Exception:
            await self._release_after_unexpected_failure(lease)
            raise

    async def _claim(
        self,
        outbox_id: UUID | None,
    ) -> tuple[LeasedCommand | None, WorkflowError | None]:
        async with self._sessions() as session, session.begin():
            return await claim_workflow_command(
                session,
                outbox_id=outbox_id,
                now=datetime.now(UTC),
                lease_seconds=self._lease_seconds,
                managed_products_enabled=self._managed_products_enabled,
            )

    async def _await_competing_dispatch(self, outbox_id: UUID) -> bool:
        """Observe a lease owner that won the narrow post-commit hand-off."""

        for attempt in range(self._handoff_poll_attempts):
            status = await self._stored_status(outbox_id)
            if status is OutboxStatus.SENT:
                return True
            if status is OutboxStatus.FAILED:
                raise WorkflowRequestRejected("dispatch_workflow_command", 409)
            if status is not OutboxStatus.PROCESSING:
                return False
            if attempt + 1 < self._handoff_poll_attempts:
                await asyncio.sleep(self._handoff_poll_seconds)
        return False

    async def _stored_status(self, outbox_id: UUID) -> OutboxStatus | None:
        async with self._sessions() as session:
            outbox = await session.get(WorkflowOutbox, outbox_id)
            return outbox.status if outbox is not None else None

    async def _finalise(
        self,
        lease: LeasedCommand,
        outcome: CommandOutcome,
    ) -> WorkflowError | None:
        async with self._sessions() as session, session.begin():
            outbox = await self._lock_current_lease(session, lease)
            if outbox is None:
                return None
            try:
                actor, work = await validated_command_state(
                    session,
                    lease.command,
                    lease.request_id,
                    managed_products_enabled=self._managed_products_enabled,
                )
            except InvalidAction:
                await mark_support_failure(session, outbox, lease.work.id)
                return WorkflowRequestRejected("finalise_workflow_command", 409)
            if isinstance(outcome, CommandRetry):
                await schedule_retry(
                    session,
                    outbox,
                    work.id,
                    max_attempts=self._max_attempts,
                )
                return outcome.error
            if isinstance(outcome, CompetingClaim):
                await project_competing_claim(
                    session,
                    outbox,
                    work,
                    outcome.task,
                )
                return outcome.error
            repository = SqlAlchemyWorkRepository(
                session,
                managed_products_enabled=self._managed_products_enabled,
            )
            if isinstance(outcome, ClaimSucceeded):
                if await repository.finalise_claim(work, actor) is None:
                    await mark_support_failure(session, outbox, work.id)
                    return WorkflowRequestRejected("finalise_claim", 409)
            elif isinstance(outcome, CompletionSucceeded):
                payload = lease.command.completion
                if payload is None:
                    await mark_support_failure(session, outbox, work.id)
                    return WorkflowRequestRejected("finalise_completion", 409)
                await repository.apply_completion(
                    work,
                    actor,
                    payload,
                    next_task=outcome.next_task,
                    reconciliation_needed=outcome.reconciliation_needed,
                    routing=lease.command.routing,
                )
            mark_sent(outbox)
            return None

    @staticmethod
    async def _lock_current_lease(
        session: AsyncSession,
        lease: LeasedCommand,
    ) -> WorkflowOutbox | None:
        return await lock_command_lease(session, lease)

    async def _release_after_unexpected_failure(
        self,
        lease: LeasedCommand,
    ) -> None:
        """Make a crashed local projection immediately recoverable."""

        try:
            async with self._sessions() as session, session.begin():
                outbox = await self._lock_current_lease(session, lease)
                if outbox is None:
                    return
                if outbox.attempts >= self._max_attempts:
                    await mark_support_failure(session, outbox, lease.work.id)
                    return
                outbox.status = OutboxStatus.PENDING
                outbox.lease_owner = None
                outbox.available_at = datetime.now(UTC)
        except Exception:
            # The durable lease expiry remains the final recovery mechanism when
            # the database itself is unavailable during crash cleanup.
            return
