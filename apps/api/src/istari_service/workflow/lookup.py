"""Bounded helpers for Camunda's eventually consistent task search."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from istari_service.workflow.engine import WorkflowEngine
from istari_service.workflow.errors import (
    AmbiguousWorkflowTask,
    UnexpectedWorkflowTask,
    WorkflowTaskNotVisible,
)
from istari_service.workflow.types import (
    ActiveTaskQuery,
    WorkflowTask,
    WorkflowTaskState,
)

Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class TaskLookupPolicy:
    """Finite retry and backoff settings for one task lookup."""

    max_attempts: int = 5
    initial_delay_seconds: float = 0.05
    backoff_multiplier: float = 2.0
    maximum_delay_seconds: float = 0.5

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds must not be negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least one")
        if self.maximum_delay_seconds < self.initial_delay_seconds:
            raise ValueError("maximum_delay_seconds must cover the initial delay")


DEFAULT_TASK_LOOKUP_POLICY = TaskLookupPolicy()


def single_active_task(
    tasks: Sequence[WorkflowTask],
    query: ActiveTaskQuery,
) -> WorkflowTask | None:
    """Validate an engine result and require it to identify at most one task."""

    for task in tasks:
        if task.process_instance_key != query.process_instance_key:
            raise UnexpectedWorkflowTask("engine returned a task for another process")
        if task.state is not WorkflowTaskState.CREATED:
            raise UnexpectedWorkflowTask("engine returned a task that is not active")
        if (
            query.expected_element_id is not None
            and task.element_id != query.expected_element_id
        ):
            raise UnexpectedWorkflowTask("engine returned an unexpected task element")
    if len(tasks) > 1:
        raise AmbiguousWorkflowTask("more than one active task matched the query")
    return tasks[0] if tasks else None


async def wait_for_active_task(
    engine: WorkflowEngine,
    query: ActiveTaskQuery,
    *,
    policy: TaskLookupPolicy = DEFAULT_TASK_LOOKUP_POLICY,
    sleep: Sleep = asyncio.sleep,
) -> WorkflowTask:
    """Wait only for the configured bound for an indexed task to appear."""

    delay = policy.initial_delay_seconds
    for attempt in range(policy.max_attempts):
        task = single_active_task(await engine.search_active_tasks(query), query)
        if task is not None:
            return task
        if attempt + 1 < policy.max_attempts:
            await sleep(delay)
            delay = min(
                delay * policy.backoff_multiplier,
                policy.maximum_delay_seconds,
            )
    raise WorkflowTaskNotVisible(
        "expected workflow task was not visible within the lookup bound"
    )
