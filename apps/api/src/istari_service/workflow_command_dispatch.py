"""Durable dispatch and recovery of human workflow commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

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
    WorkflowConflict,
    WorkflowEngineUnavailable,
    WorkflowError,
    WorkflowRequestRejected,
    WorkflowTaskNotFound,
    WorkflowTaskNotVisible,
)
from istari_service.workflow.lookup import TaskLookupPolicy, wait_for_active_task
from istari_service.workflow.projection import (
    element_id_for_status,
    status_after_action,
)
from istari_service.workflow.types import (
    ActiveTaskQuery,
    ClaimTaskCommand,
    ProcessStateQuery,
    WorkflowAction,
    WorkflowProcessState,
    WorkflowTask,
)
from istari_service.workflow_command_results import (
    mark_sent,
    mark_support_failure,
    project_competing_claim,
    schedule_retry,
    stored_work_id,
)
from istari_service.workflow_command_state import (
    completion_engine_command,
    validated_command_state,
)

DEFAULT_COMMAND_LOOKUP = TaskLookupPolicy()
COMMAND_TYPES = tuple(command.value for command in WorkCommandType)


class WorkflowCommandDispatcher:
    """Execute one committed intent and atomically project the proven outcome."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        engine: WorkflowEngine,
        *,
        lookup_policy: TaskLookupPolicy = DEFAULT_COMMAND_LOOKUP,
        max_attempts: int = 30,
        lease_seconds: int = 30,
    ) -> None:
        self._sessions = session_factory
        self._engine = engine
        self._lookup_policy = lookup_policy
        self._max_attempts = max_attempts
        self._lease_seconds = lease_seconds

    async def dispatch(self, outbox_id: UUID) -> bool:
        processed, error = await self._run(outbox_id)
        if error is not None:
            raise error
        return processed

    async def dispatch_once(self) -> bool:
        processed, _error = await self._run(None)
        return processed

    async def _run(self, outbox_id: UUID | None) -> tuple[bool, WorkflowError | None]:
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
                return False, None
            outbox.status = OutboxStatus.PROCESSING
            outbox.attempts += 1
            outbox.available_at = now + timedelta(seconds=self._lease_seconds)
            try:
                command = parse_command(
                    outbox.id,
                    outbox.event_type,
                    outbox.payload,
                    outbox.attempts,
                )
                actor, work = await validated_command_state(
                    session, command, outbox.request_id
                )
                if command.command_type is WorkCommandType.CLAIM_TASK:
                    error = await self._claim(session, outbox, command, actor, work)
                else:
                    error = await self._complete(session, outbox, command, actor, work)
            except (InvalidAction, KeyError, TypeError, ValueError, ValidationError):
                await mark_support_failure(
                    session, outbox, stored_work_id(outbox.payload)
                )
                error = WorkflowRequestRejected("dispatch_workflow_command", 409)
            return True, error

    async def _claim(
        self,
        session: AsyncSession,
        outbox: WorkflowOutbox,
        command: PendingWorkCommand,
        actor: Actor,
        work: WorkRecord,
    ) -> WorkflowError | None:
        try:
            await self._engine.claim_task(ClaimTaskCommand(command.task_key, actor.id))
        except (WorkflowConflict, WorkflowTaskNotFound) as error:
            recovered = await self._recover_claim(session, outbox, command, actor, work)
            if recovered:
                return None
            if outbox.status is OutboxStatus.PENDING:
                return WorkflowEngineUnavailable("claim recovery is pending")
            return error
        except WorkflowError as error:
            await schedule_retry(
                session, outbox, work.id, max_attempts=self._max_attempts
            )
            return error
        result = await SqlAlchemyWorkRepository(session).finalise_claim(work, actor)
        if result is None:
            await mark_support_failure(session, outbox, work.id)
            return WorkflowRequestRejected("finalise_claim", 409)
        mark_sent(outbox)
        return None

    async def _recover_claim(
        self,
        session: AsyncSession,
        outbox: WorkflowOutbox,
        command: PendingWorkCommand,
        actor: Actor,
        work: WorkRecord,
    ) -> bool:
        try:
            task = await wait_for_active_task(
                self._engine,
                ActiveTaskQuery(command.process_instance_key, command.element_id),
                policy=self._lookup_policy,
            )
        except WorkflowError:
            await schedule_retry(
                session, outbox, work.id, max_attempts=self._max_attempts
            )
            return False
        if task.task_key != command.task_key or task.assignee is None:
            await schedule_retry(
                session, outbox, work.id, max_attempts=self._max_attempts
            )
            return False
        if task.assignee == str(command.actor_id):
            await SqlAlchemyWorkRepository(session).finalise_claim(work, actor)
            mark_sent(outbox)
            return True
        await project_competing_claim(session, outbox, work, task)
        return False

    async def _complete(
        self,
        session: AsyncSession,
        outbox: WorkflowOutbox,
        command: PendingWorkCommand,
        actor: Actor,
        work: WorkRecord,
    ) -> WorkflowError | None:
        payload = command.completion
        if payload is None:
            raise InvalidAction()
        action = WorkflowAction(payload.action)
        next_status = status_after_action(work.request.status, action)
        expected_element = element_id_for_status(next_status)
        recovered = False
        try:
            await self._engine.complete_task(completion_engine_command(command))
        except (WorkflowConflict, WorkflowTaskNotFound):
            recovered = True
        except WorkflowError as error:
            await schedule_retry(
                session, outbox, work.id, max_attempts=self._max_attempts
            )
            return error
        try:
            next_task = await self._completion_proof(
                command, expected_element, recovered
            )
        except WorkflowError as error:
            await schedule_retry(
                session, outbox, work.id, max_attempts=self._max_attempts
            )
            return error
        detail = await SqlAlchemyWorkRepository(session).apply_completion(
            work,
            actor,
            payload,
            next_task=next_task,
            reconciliation_needed=expected_element is not None and next_task is None,
            routing=command.routing,
        )
        del detail
        mark_sent(outbox)
        return None

    async def _completion_proof(
        self,
        command: PendingWorkCommand,
        expected_element: str | None,
        recovered: bool,
    ) -> WorkflowTask | None:
        if expected_element is not None:
            try:
                return await wait_for_active_task(
                    self._engine,
                    ActiveTaskQuery(command.process_instance_key, expected_element),
                    policy=self._lookup_policy,
                )
            except WorkflowTaskNotVisible:
                if not recovered:
                    return None
                raise
        if not recovered:
            return None
        process = await self._engine.find_process_state(
            ProcessStateQuery(command.process_instance_key)
        )
        if process is None or process.state != WorkflowProcessState.COMPLETED:
            raise WorkflowTaskNotVisible("terminal process state is not proven")
        return None
