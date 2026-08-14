"""Transactional start-outbox dispatch and task-projection reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.model_enums import (
    RequestStatus,
    WorkflowInstanceStatus,
    WorkflowTaskStatus,
)
from istari_service.models import (
    OutboxStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowOutbox,
)
from istari_service.models import (
    WorkflowTask as StoredWorkflowTask,
)
from istari_service.ownership import OWNER_BY_STATUS
from istari_service.policies import ROLE_BY_STAGE
from istari_service.repositories.event_store import append_request_event
from istari_service.request_event_audience import RequestEventAudience
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow.errors import (
    WorkflowConflict,
    WorkflowContractError,
    WorkflowError,
    WorkflowTaskNotVisible,
)
from istari_service.workflow.lookup import TaskLookupPolicy, wait_for_active_task
from istari_service.workflow.projection import (
    FIRST_TASK_RECONCILIATION_MESSAGE,
    INTAKE_REVIEW_ELEMENT_ID,
)
from istari_service.workflow.types import (
    ActiveTaskQuery,
    StartedProcess,
    StartedProcessQuery,
    StartProcessCommand,
    WorkflowTask,
)
from istari_service.workflow_start_lease import (
    PendingStart,
    claim_pending_start,
    lock_start_lease,
)

DEFAULT_START_LOOKUP_POLICY = TaskLookupPolicy()


class WorkflowOutboxDispatcher:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        engine: WorkflowEngine,
        *,
        process_id: str,
        lookup_policy: TaskLookupPolicy = DEFAULT_START_LOOKUP_POLICY,
        max_attempts: int = 30,
    ) -> None:
        self._sessions = session_factory
        self._engine = engine
        self._process_id = process_id
        self._lookup_policy = lookup_policy
        self._max_attempts = max_attempts

    async def dispatch_once(self) -> bool:
        pending = await self._claim_next()
        if pending is None:
            return False
        command = StartProcessCommand(
            process_definition_id=pending.process_id,
            request_id=pending.request_id,
            requester_id=pending.requester_id,
            process_definition_version=pending.process_version,
        )
        try:
            started = await self._start_idempotently(command)
            self._validate_started_identity(pending, started)
            task = await self._find_initial_task(started)
            await self._record_success(pending, started, task)
        except WorkflowTaskNotVisible:
            await self._record_success(pending, started, None)
        except WorkflowError:
            await self._record_retry(pending)
        return True

    @staticmethod
    def _validate_started_identity(
        pending: PendingStart,
        started: StartedProcess,
    ) -> None:
        if (
            started.business_id != str(pending.request_id)
            or started.process_definition_id != pending.process_id
            or (
                pending.process_version != -1
                and started.process_definition_version != pending.process_version
            )
        ):
            raise WorkflowContractError(
                "The started workflow does not match the immutable request pin."
            )

    async def _claim_next(self) -> PendingStart | None:
        async with self._sessions() as session, session.begin():
            return await claim_pending_start(
                session,
                legacy_process_id=self._process_id,
                now=datetime.now(UTC),
            )

    async def _start_idempotently(
        self,
        command: StartProcessCommand,
    ) -> StartedProcess:
        try:
            return await self._engine.start_process(command)
        except WorkflowConflict:
            existing = await self._engine.find_started_process(
                StartedProcessQuery.from_start(command)
            )
            if existing is None:
                raise
            return existing

    async def _find_initial_task(self, started: StartedProcess) -> WorkflowTask:
        return await wait_for_active_task(
            self._engine,
            ActiveTaskQuery(
                started.process_instance_key,
                INTAKE_REVIEW_ELEMENT_ID,
            ),
            policy=self._lookup_policy,
        )

    async def _record_success(
        self,
        pending: PendingStart,
        started: StartedProcess,
        task: WorkflowTask | None,
    ) -> None:
        async with self._sessions() as session, session.begin():
            outbox = await self._lock_current_lease(session, pending)
            if outbox is None:
                return
            request = await session.get(ServiceRequest, pending.request_id)
            instance = await session.scalar(
                select(WorkflowInstance).where(
                    WorkflowInstance.request_id == pending.request_id
                )
            )
            if request is None or instance is None:
                return
            now = datetime.now(UTC)
            instance.process_definition_key = started.process_definition_key
            instance.process_version = started.process_definition_version
            instance.process_instance_key = started.process_instance_key
            instance.status = WorkflowInstanceStatus.ACTIVE
            instance.started_at = instance.started_at or now
            instance.current_element_id = task.element_id if task else None
            instance.last_reconciled_at = now if task else None
            instance.last_error = None
            cancelled = request.status is RequestStatus.CANCELLED
            if request.status == RequestStatus.ROUTING_PENDING:
                request.status = RequestStatus.TRIAGE_REVIEW
                request.current_owner = OWNER_BY_STATUS[RequestStatus.TRIAGE_REVIEW]
                request.version += 1
                request.workflow_error = (
                    None if task else FIRST_TASK_RECONCILIATION_MESSAGE
                )
                await append_request_event(
                    session,
                    request_id=request.id,
                    actor_id=None,
                    event_type="workflow_started",
                    message="Request entered intake review.",
                    prior_status=RequestStatus.ROUTING_PENDING,
                    next_status=RequestStatus.TRIAGE_REVIEW,
                    audience=RequestEventAudience.CUSTOMER_AND_STAFF,
                )
            if task is not None and not cancelled:
                await self._add_projection(session, request, instance, task)
            if cancelled:
                instance.current_element_id = None
            outbox.status = OutboxStatus.SENT
            outbox.lease_owner = None
            outbox.sent_at = now
            outbox.last_error = None

    async def _record_retry(self, pending: PendingStart) -> None:
        async with self._sessions() as session, session.begin():
            outbox = await self._lock_current_lease(session, pending)
            if outbox is None:
                return
            request = await session.get(ServiceRequest, pending.request_id)
            instance = await session.scalar(
                select(WorkflowInstance).where(
                    WorkflowInstance.request_id == pending.request_id
                )
            )
            exhausted = pending.attempts >= self._max_attempts
            outbox.status = OutboxStatus.FAILED if exhausted else OutboxStatus.PENDING
            outbox.lease_owner = None
            outbox.available_at = datetime.now(UTC) + timedelta(
                seconds=min(2**pending.attempts, 30)
            )
            outbox.last_error = "Workflow start is unavailable."
            if request is not None:
                request.workflow_error = (
                    "Workflow start needs support."
                    if exhausted
                    else "Workflow start will be retried."
                )
            if instance is not None:
                instance.status = (
                    WorkflowInstanceStatus.ERROR
                    if exhausted
                    else WorkflowInstanceStatus.START_PENDING
                )
                instance.last_error = outbox.last_error

    @staticmethod
    async def _lock_current_lease(
        session: AsyncSession,
        pending: PendingStart,
    ) -> WorkflowOutbox | None:
        """Compare and lock a lease so a superseded worker cannot finalise it."""

        return await lock_start_lease(session, pending)

    @staticmethod
    async def _add_projection(
        session: AsyncSession,
        request: ServiceRequest,
        instance: WorkflowInstance,
        task: WorkflowTask,
    ) -> None:
        existing = await session.scalar(
            select(StoredWorkflowTask.id).where(
                StoredWorkflowTask.task_key == task.task_key
            )
        )
        if existing is not None:
            return
        assignee_id: UUID | None = None
        if task.assignee:
            try:
                assignee_id = UUID(task.assignee)
            except ValueError:
                assignee_id = None
        status = WorkflowTaskStatus.CLAIMED if assignee_id else WorkflowTaskStatus.OPEN
        session.add(
            StoredWorkflowTask(
                request_id=request.id,
                workflow_instance_id=instance.id,
                task_key=task.task_key,
                element_id=task.element_id,
                name=task.element_id.replace("_", " ").title(),
                candidate_role=ROLE_BY_STAGE[request.status],
                expected_status=request.status,
                status=status,
                assignee_user_id=assignee_id,
                claimed_at=datetime.now(UTC) if assignee_id else None,
            )
        )
