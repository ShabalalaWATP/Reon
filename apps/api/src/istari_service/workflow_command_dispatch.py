"""Fenced dispatch and recovery of durable human workflow commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.domain import Actor, WorkRecord
from istari_service.errors import InvalidAction
from istari_service.models import OutboxStatus, WorkflowOutbox
from istari_service.repositories.work import SqlAlchemyWorkRepository
from istari_service.work_command_types import (
    PendingWorkCommand,
    WorkCommandType,
    parse_command,
)
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow.errors import (
    WorkflowError,
    WorkflowRequestRejected,
)
from istari_service.workflow.lookup import TaskLookupPolicy
from istari_service.workflow_command_execution import (
    ClaimSucceeded,
    CommandOutcome,
    CommandRetry,
    CompetingClaim,
    CompletionSucceeded,
    WorkflowCommandExecutor,
)
from istari_service.workflow_command_results import (
    mark_sent,
    mark_support_failure,
    project_competing_claim,
    schedule_retry,
    stored_work_id,
)
from istari_service.workflow_command_state import validated_command_state

DEFAULT_COMMAND_LOOKUP = TaskLookupPolicy()
COMMAND_TYPES = tuple(command.value for command in WorkCommandType)


@dataclass(frozen=True, slots=True)
class LeasedCommand:
    request_id: UUID
    lease_owner: str
    lease_generation: int
    command: PendingWorkCommand
    actor: Actor
    work: WorkRecord


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
    ) -> None:
        self._sessions = session_factory
        self._executor = WorkflowCommandExecutor(engine, lookup_policy)
        self._max_attempts = max_attempts
        self._lease_seconds = lease_seconds
        self._managed_products_enabled = managed_products_enabled

    async def dispatch(self, outbox_id: UUID) -> bool:
        processed, error = await self._run(outbox_id)
        if error is not None:
            raise error
        return processed

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
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            query = (
                select(WorkflowOutbox)
                .where(
                    WorkflowOutbox.event_type.in_(COMMAND_TYPES),
                    WorkflowOutbox.available_at <= now,
                    or_(
                        WorkflowOutbox.status == OutboxStatus.PENDING,
                        WorkflowOutbox.status == OutboxStatus.PROCESSING,
                    ),
                )
                .order_by(WorkflowOutbox.created_at, WorkflowOutbox.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if outbox_id is not None:
                query = query.where(WorkflowOutbox.id == outbox_id)
            outbox = await session.scalar(query)
            if outbox is None:
                return None, None
            owner = uuid4().hex
            outbox.status = OutboxStatus.PROCESSING
            outbox.attempts += 1
            outbox.lease_owner = owner
            outbox.lease_generation += 1
            outbox.available_at = now + timedelta(seconds=self._lease_seconds)
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
                    managed_products_enabled=self._managed_products_enabled,
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
        current: WorkflowOutbox | None = await session.scalar(
            select(WorkflowOutbox)
            .where(
                WorkflowOutbox.id == lease.command.outbox_id,
                WorkflowOutbox.status == OutboxStatus.PROCESSING,
                WorkflowOutbox.lease_owner == lease.lease_owner,
                WorkflowOutbox.lease_generation == lease.lease_generation,
            )
            .with_for_update()
        )
        return current

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
