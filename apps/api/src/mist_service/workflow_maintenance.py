"""Reconcile eventually consistent workflow tasks."""

from __future__ import annotations

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
from mist_service.workflow.engine import WorkflowEngine
from mist_service.workflow.errors import WorkflowError
from mist_service.workflow.projection import (
    RECONCILIATION_MESSAGES,
    element_id_for_status,
    status_for_element,
)
from mist_service.workflow.types import ActiveTaskQuery
from mist_service.workflow_dispatch import (
    add_task_projection,
)


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
