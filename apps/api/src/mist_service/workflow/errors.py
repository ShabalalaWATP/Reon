"""Errors exposed by workflow ports, adapters and projection helpers."""

from __future__ import annotations


class WorkflowError(RuntimeError):
    """Base error for workflow integration failures."""


class WorkflowEngineUnavailable(WorkflowError):
    """The engine could not safely accept or answer a request."""


class WorkflowContractError(WorkflowError):
    """The engine returned a response outside the pinned V2 contract."""


class WorkflowRequestRejected(WorkflowError):
    """The engine rejected a well-formed integration request."""

    def __init__(self, operation: str, status_code: int) -> None:
        self.operation = operation
        self.status_code = status_code
        message = f"workflow operation {operation!r} returned HTTP {status_code}"
        super().__init__(message)


class WorkflowConflict(WorkflowRequestRejected):
    """A command conflicts with the current engine state or business ID."""


class WorkflowTaskNotFound(WorkflowRequestRejected):
    """The requested task key does not exist in the engine."""


class WorkflowTaskNotVisible(WorkflowError):
    """An expected task did not become searchable within the retry bound."""


class AmbiguousWorkflowTask(WorkflowError):
    """More than one active task matched a query that must identify one task."""


class AmbiguousWorkflowProcess(WorkflowError):
    """More than one process matched a supposedly unique request business ID."""


class WorkflowProcessNotVisible(WorkflowError):
    """A conflicted process start did not become searchable within the bound."""


class UnexpectedWorkflowTask(WorkflowError):
    """A task does not match the process instance or element being completed."""


class UnknownWorkflowElement(WorkflowError):
    """A BPMN element has no explicit application status projection."""


class InvalidWorkflowTransition(WorkflowError):
    """An action is not valid for the current projected status."""
