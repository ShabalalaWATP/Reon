"""Async port implemented by real and deterministic workflow engines."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mist_service.workflow.types import (
    ActiveTaskQuery,
    CancelProcessCommand,
    ClaimTaskCommand,
    CompleteTaskCommand,
    ProcessStateQuery,
    StartedProcess,
    StartedProcessQuery,
    StartProcessCommand,
    WorkflowProcessSnapshot,
    WorkflowTask,
)


@runtime_checkable
class WorkflowEngine(Protocol):
    """Application-facing workflow operations with no persistence dependency."""

    async def is_reachable(self) -> bool:
        """Return engine reachability for readiness reporting, never liveness."""
        ...

    async def start_process(self, command: StartProcessCommand) -> StartedProcess:
        """Start the process for one opaque request identifier."""
        ...

    async def find_started_process(
        self,
        query: StartedProcessQuery,
    ) -> StartedProcess | None:
        """Find an existing process after an uncertain or conflicting start."""
        ...

    async def find_process_state(
        self,
        query: ProcessStateQuery,
    ) -> WorkflowProcessSnapshot | None:
        """Find minimal state evidence for one exact process instance."""
        ...

    async def search_active_tasks(
        self,
        query: ActiveTaskQuery,
    ) -> tuple[WorkflowTask, ...]:
        """Search the eventually consistent active-task index."""
        ...

    async def claim_task(self, command: ClaimTaskCommand) -> None:
        """Atomically claim an unassigned task without overriding another user."""
        ...

    async def complete_task(self, command: CompleteTaskCommand) -> None:
        """Complete the exact expected task with a human-selected action."""
        ...

    async def cancel_process(self, command: CancelProcessCommand) -> None:
        """Terminate one exact active process instance."""
        ...
