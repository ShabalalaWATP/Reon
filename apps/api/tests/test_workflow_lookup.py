"""Unit coverage for bounded, eventually consistent task lookup."""

from __future__ import annotations

import pytest

from mist_service.workflow.errors import (
    AmbiguousWorkflowTask,
    UnexpectedWorkflowTask,
    WorkflowTaskNotVisible,
)
from mist_service.workflow.lookup import (
    TaskLookupPolicy,
    single_active_task,
    wait_for_active_task,
)
from mist_service.workflow.types import (
    ActiveTaskQuery,
    WorkflowTask,
    WorkflowTaskState,
)


def task(
    *,
    task_key: str = "task-1",
    process_key: str = "process-1",
    element_id: str = "intake_review",
    state: WorkflowTaskState = WorkflowTaskState.CREATED,
) -> WorkflowTask:
    return WorkflowTask(task_key, process_key, element_id, state)


class SearchEngine:
    def __init__(self, responses: list[tuple[WorkflowTask, ...]]) -> None:
        self.responses = responses
        self.queries: list[ActiveTaskQuery] = []

    async def search_active_tasks(
        self,
        query: ActiveTaskQuery,
    ) -> tuple[WorkflowTask, ...]:
        self.queries.append(query)
        return self.responses.pop(0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"initial_delay_seconds": -0.1},
        {"backoff_multiplier": 0.9},
        {"initial_delay_seconds": 1.0, "maximum_delay_seconds": 0.5},
    ],
)
def test_lookup_policy_rejects_unbounded_or_invalid_values(
    kwargs: dict[str, float | int],
) -> None:
    with pytest.raises(ValueError):
        TaskLookupPolicy(**kwargs)


def test_single_active_task_validates_every_returned_task() -> None:
    query = ActiveTaskQuery("process-1", "intake_review")
    expected = task()

    assert single_active_task((), query) is None
    assert single_active_task((expected,), query) is expected
    with pytest.raises(UnexpectedWorkflowTask, match="another process"):
        single_active_task((task(process_key="process-2"),), query)
    with pytest.raises(UnexpectedWorkflowTask, match="not active"):
        single_active_task((task(state=WorkflowTaskState.COMPLETED),), query)
    with pytest.raises(UnexpectedWorkflowTask, match="element"):
        single_active_task((task(element_id="coordination_review"),), query)
    with pytest.raises(AmbiguousWorkflowTask, match="more than one"):
        single_active_task((expected, task(task_key="task-2")), query)


@pytest.mark.asyncio
async def test_wait_for_active_task_uses_bounded_capped_backoff() -> None:
    expected = task()
    engine = SearchEngine([(), (), (expected,)])
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    query = ActiveTaskQuery("process-1", "intake_review")
    result = await wait_for_active_task(
        engine,  # type: ignore[arg-type]
        query,
        policy=TaskLookupPolicy(
            max_attempts=3,
            initial_delay_seconds=0.1,
            backoff_multiplier=10,
            maximum_delay_seconds=0.15,
        ),
        sleep=record_sleep,
    )

    assert result is expected
    assert sleeps == [0.1, 0.15]
    assert engine.queries == [query, query, query]


@pytest.mark.asyncio
async def test_wait_for_active_task_stops_at_attempt_bound() -> None:
    engine = SearchEngine([(), ()])
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    with pytest.raises(WorkflowTaskNotVisible, match="lookup bound"):
        await wait_for_active_task(
            engine,  # type: ignore[arg-type]
            ActiveTaskQuery("process-1"),
            policy=TaskLookupPolicy(max_attempts=2, initial_delay_seconds=0.2),
            sleep=record_sleep,
        )
    assert sleeps == [0.2]
