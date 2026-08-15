"""Reconcile eventually consistent tasks and run workflow maintenance."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.models import (
    RequestStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowInstanceStatus,
)
from mist_service.ownership import OWNER_BY_STATUS
from mist_service.request_event_projection import NotificationProjectionReconciler
from mist_service.workflow.engine import WorkflowEngine
from mist_service.workflow.errors import WorkflowError
from mist_service.workflow.projection import (
    RECONCILIATION_MESSAGES,
    element_id_for_status,
    status_for_element,
)
from mist_service.workflow.types import ActiveTaskQuery
from mist_service.workflow_command_dispatch import WorkflowCommandDispatcher
from mist_service.workflow_dispatch import (
    WorkflowOutboxDispatcher,
    add_task_projection,
)

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class WorkflowMaintenanceHealth:
    running: bool = True
    consecutive_failures: int = 0
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None

    @property
    def ready(self) -> bool:
        return self.running and self.consecutive_failures < 3


@dataclass(frozen=True, slots=True)
class ReconciliationCandidate:
    request_id: UUID
    status: RequestStatus
    version: int
    process_key: str
    expected_element: str


class WorkflowReconciler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        engine: WorkflowEngine,
    ) -> None:
        self._sessions = session_factory
        self._engine = engine

    async def reconcile_once(self) -> bool:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(ServiceRequest, WorkflowInstance)
                    .join(
                        WorkflowInstance,
                        WorkflowInstance.request_id == ServiceRequest.id,
                    )
                    .where(
                        WorkflowInstance.status == WorkflowInstanceStatus.ACTIVE,
                        ServiceRequest.workflow_error.in_(RECONCILIATION_MESSAGES),
                    )
                    .order_by(ServiceRequest.updated_at)
                    .limit(1)
                )
            ).one_or_none()
            if row is None or row[1].process_instance_key is None:
                return False
            expected_element = element_id_for_status(row[0].status)
            if expected_element is None:
                return False
            candidate = ReconciliationCandidate(
                request_id=row[0].id,
                status=row[0].status,
                version=row[0].version,
                process_key=row[1].process_instance_key,
                expected_element=expected_element,
            )
        try:
            tasks = await self._engine.search_active_tasks(
                ActiveTaskQuery(candidate.process_key, candidate.expected_element)
            )
        except WorkflowError:
            return False
        if len(tasks) != 1:
            return False
        task = tasks[0]
        if (
            task.process_instance_key != candidate.process_key
            or task.element_id != candidate.expected_element
        ):
            return False
        async with self._sessions() as session, session.begin():
            row = (
                await session.execute(
                    select(ServiceRequest, WorkflowInstance)
                    .join(
                        WorkflowInstance,
                        WorkflowInstance.request_id == ServiceRequest.id,
                    )
                    .where(ServiceRequest.id == candidate.request_id)
                    .with_for_update()
                )
            ).one_or_none()
            if row is None:
                return False
            request, instance = row
            if not self._is_current_candidate(request, instance, candidate):
                return False
            projected = status_for_element(task.element_id)
            if request.status == RequestStatus.REWORK_REQUIRED:
                projected = RequestStatus.REWORK_REQUIRED
            if request.status != projected:
                request.version += 1
            request.status = projected
            request.current_owner = OWNER_BY_STATUS[projected]
            request.workflow_error = None
            instance.current_element_id = task.element_id
            instance.last_reconciled_at = datetime.now(UTC)
            await add_task_projection(session, request, instance, task)
        return True

    @staticmethod
    def _is_current_candidate(
        request: ServiceRequest,
        instance: WorkflowInstance,
        candidate: ReconciliationCandidate,
    ) -> bool:
        return (
            request.status == candidate.status
            and request.version == candidate.version
            and request.workflow_error in RECONCILIATION_MESSAGES
            and instance.status == WorkflowInstanceStatus.ACTIVE
            and instance.process_instance_key == candidate.process_key
            and element_id_for_status(request.status) == candidate.expected_element
        )


async def run_workflow_maintenance(
    dispatcher: WorkflowOutboxDispatcher,
    reconciler: WorkflowReconciler,
    stop: asyncio.Event,
    *,
    command_dispatcher: WorkflowCommandDispatcher | None = None,
    notification_reconciler: NotificationProjectionReconciler | None = None,
    interval_seconds: float = 0.5,
    health: WorkflowMaintenanceHealth | None = None,
) -> None:
    """Run bounded maintenance without delaying API liveness."""

    state = health or WorkflowMaintenanceHealth()
    state.running = True
    try:
        while not stop.is_set():
            try:
                worked = await dispatcher.dispatch_once()
                command_worked = (
                    await command_dispatcher.dispatch_once()
                    if command_dispatcher is not None
                    else False
                )
                reconciled = await reconciler.reconcile_once()
                notifications_reconciled = (
                    await notification_reconciler.reconcile_once()
                    if notification_reconciler is not None
                    else False
                )
            except Exception:
                state.consecutive_failures += 1
                state.last_failure_at = datetime.now(UTC)
                LOGGER.exception("Workflow maintenance iteration failed.")
                await _wait_for_next_iteration(stop, interval_seconds)
                continue
            state.consecutive_failures = 0
            state.last_success_at = datetime.now(UTC)
            if worked or command_worked or reconciled or notifications_reconciled:
                continue
            await _wait_for_next_iteration(stop, interval_seconds)
    finally:
        state.running = False


async def _wait_for_next_iteration(
    stop: asyncio.Event,
    interval_seconds: float,
) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
    except TimeoutError:
        return
