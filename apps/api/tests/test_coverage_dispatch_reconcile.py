"""Workflow reconciler candidate and eventual-consistency edge coverage."""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

import pytest
from sqlalchemy import select

from conftest import ApiHarness, request_payload
from istari_service.models import (
    RequestStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowInstanceStatus,
)
from istari_service.models import (
    WorkflowTask as StoredWorkflowTask,
)
from istari_service.repositories.work import OWNER_BY_STATUS
from istari_service.repositories.work_intents import PENDING_MESSAGE
from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow.errors import WorkflowEngineUnavailable, WorkflowError
from istari_service.workflow.projection import NEXT_TASK_RECONCILIATION_MESSAGE
from istari_service.workflow.types import (
    ActiveTaskQuery,
    WorkflowTask,
    WorkflowTaskState,
)
from istari_service.workflow_maintenance import WorkflowReconciler


async def create_request(harness: ApiHarness) -> UUID:
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


async def prepare_candidate(
    harness: ApiHarness,
    *,
    status: RequestStatus = RequestStatus.TRIAGE_REVIEW,
    process_key: str | None = "synthetic-process-key",
) -> UUID:
    request_id = await create_request(harness)
    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        assert request is not None and instance is not None
        request.status = status
        request.workflow_error = NEXT_TASK_RECONCILIATION_MESSAGE
        instance.status = WorkflowInstanceStatus.ACTIVE
        instance.process_instance_key = process_key
    return request_id


def workflow_task(
    *,
    element_id: str = "intake_review",
    suffix: str = "reconcile",
) -> WorkflowTask:
    return WorkflowTask(
        task_key=f"synthetic-task-{suffix}",
        process_instance_key="synthetic-process-key",
        element_id=element_id,
        state=WorkflowTaskState.CREATED,
    )


class SearchEngine:
    def __init__(
        self,
        tasks: tuple[WorkflowTask, ...] = (),
        error: WorkflowError | None = None,
    ) -> None:
        self.tasks = tasks
        self.error = error
        self.queries: list[ActiveTaskQuery] = []

    async def search_active_tasks(
        self, query: ActiveTaskQuery
    ) -> tuple[WorkflowTask, ...]:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return self.tasks


class DeletingSearchEngine(SearchEngine):
    def __init__(
        self,
        harness: ApiHarness,
        request_id: UUID,
        target: Literal["request", "instance"],
    ) -> None:
        super().__init__((workflow_task(),))
        self.harness = harness
        self.request_id = request_id
        self.target = target

    async def search_active_tasks(
        self, query: ActiveTaskQuery
    ) -> tuple[WorkflowTask, ...]:
        async with self.harness.sessions() as session, session.begin():
            if self.target == "request":
                entity = await session.get(ServiceRequest, self.request_id)
            else:
                entity = await session.scalar(
                    select(WorkflowInstance).where(
                        WorkflowInstance.request_id == self.request_id
                    )
                )
            assert entity is not None
            await session.delete(entity)
        return await super().search_active_tasks(query)


class MutatingSearchEngine(SearchEngine):
    def __init__(
        self,
        harness: ApiHarness,
        request_id: UUID,
        mutation: Literal["status", "version", "process_key", "instance_status"],
    ) -> None:
        super().__init__((workflow_task(),))
        self.harness = harness
        self.request_id = request_id
        self.mutation = mutation

    async def search_active_tasks(
        self, query: ActiveTaskQuery
    ) -> tuple[WorkflowTask, ...]:
        async with self.harness.sessions() as session, session.begin():
            request = await session.get(ServiceRequest, self.request_id)
            instance = await session.scalar(
                select(WorkflowInstance).where(
                    WorkflowInstance.request_id == self.request_id
                )
            )
            assert request is not None and instance is not None
            if self.mutation == "status":
                request.status = RequestStatus.COORDINATION_REVIEW
            elif self.mutation == "version":
                request.version += 1
            elif self.mutation == "process_key":
                instance.process_instance_key = "replacement-process-key"
            else:
                instance.status = WorkflowInstanceStatus.ERROR
        return await super().search_active_tasks(query)


async def test_reconciler_skips_absent_candidate_and_missing_process_key(
    api_harness: ApiHarness,
) -> None:
    reconciler = WorkflowReconciler(api_harness.sessions, api_harness.workflow)
    assert not await reconciler.reconcile_once()

    await prepare_candidate(api_harness, process_key=None)
    assert not await reconciler.reconcile_once()


async def test_reconciler_does_not_race_a_pending_command(
    api_harness: ApiHarness,
) -> None:
    request_id = await prepare_candidate(api_harness)
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.workflow_error = PENDING_MESSAGE
    engine = SearchEngine((workflow_task(),))

    assert not await WorkflowReconciler(
        api_harness.sessions, cast(WorkflowEngine, engine)
    ).reconcile_once()
    assert engine.queries == []


async def test_reconciler_skips_status_without_active_task(
    api_harness: ApiHarness,
) -> None:
    await prepare_candidate(api_harness, status=RequestStatus.COMPLETED)

    assert not await WorkflowReconciler(
        api_harness.sessions, api_harness.workflow
    ).reconcile_once()


async def test_reconciler_handles_engine_failure(api_harness: ApiHarness) -> None:
    await prepare_candidate(api_harness)
    engine = SearchEngine(error=WorkflowEngineUnavailable("synthetic outage"))
    reconciler = WorkflowReconciler(api_harness.sessions, cast(WorkflowEngine, engine))

    assert not await reconciler.reconcile_once()
    assert engine.queries == [ActiveTaskQuery("synthetic-process-key", "intake_review")]


@pytest.mark.parametrize("task_count", [0, 2])
async def test_reconciler_requires_exactly_one_task(
    api_harness: ApiHarness,
    task_count: int,
) -> None:
    await prepare_candidate(api_harness)
    tasks = tuple(workflow_task(suffix=str(index)) for index in range(task_count))
    engine = SearchEngine(tasks)

    assert not await WorkflowReconciler(
        api_harness.sessions, cast(WorkflowEngine, engine)
    ).reconcile_once()


@pytest.mark.parametrize("target", ["request", "instance"])
async def test_reconciler_tolerates_entity_removed_after_search(
    api_harness: ApiHarness,
    target: Literal["request", "instance"],
) -> None:
    request_id = await prepare_candidate(api_harness)
    engine = DeletingSearchEngine(api_harness, request_id, target)

    assert not await WorkflowReconciler(
        api_harness.sessions, cast(WorkflowEngine, engine)
    ).reconcile_once()


async def test_reconciler_preserves_rework_status_for_delivery_task(
    api_harness: ApiHarness,
) -> None:
    request_id = await prepare_candidate(
        api_harness, status=RequestStatus.REWORK_REQUIRED
    )
    task = workflow_task(element_id="delivery_work")
    engine = SearchEngine((task,))

    assert await WorkflowReconciler(
        api_harness.sessions, cast(WorkflowEngine, engine)
    ).reconcile_once()

    async with api_harness.sessions() as session:
        request = await session.get(ServiceRequest, request_id)
        instance = await session.scalar(
            select(WorkflowInstance).where(WorkflowInstance.request_id == request_id)
        )
        projection = await session.scalar(
            select(StoredWorkflowTask).where(
                StoredWorkflowTask.task_key == task.task_key
            )
        )
        assert request is not None and instance is not None and projection is not None
        assert request.status == RequestStatus.REWORK_REQUIRED
        assert request.current_owner == OWNER_BY_STATUS[RequestStatus.REWORK_REQUIRED]
        assert request.workflow_error is None
        assert instance.current_element_id == "delivery_work"
        assert instance.last_reconciled_at is not None
        assert projection.expected_status == RequestStatus.REWORK_REQUIRED


@pytest.mark.parametrize(
    "mutation",
    ["status", "version", "process_key", "instance_status"],
)
async def test_reconciler_rejects_candidate_changed_during_engine_search(
    api_harness: ApiHarness,
    mutation: Literal["status", "version", "process_key", "instance_status"],
) -> None:
    request_id = await prepare_candidate(api_harness)
    engine = MutatingSearchEngine(api_harness, request_id, mutation)

    assert not await WorkflowReconciler(
        api_harness.sessions,
        cast(WorkflowEngine, engine),
    ).reconcile_once()

    async with api_harness.sessions() as session:
        request = await session.get(ServiceRequest, request_id)
        projections = (
            await session.scalars(
                select(StoredWorkflowTask).where(
                    StoredWorkflowTask.request_id == request_id
                )
            )
        ).all()
        assert request is not None
        assert request.workflow_error == NEXT_TASK_RECONCILIATION_MESSAGE
        assert projections == []
