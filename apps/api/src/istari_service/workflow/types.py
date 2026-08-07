"""Typed values exchanged across the workflow-engine boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class WorkflowAction(StrEnum):
    """Human-selected route results accepted by the executable process."""

    REQUEST_INFORMATION = "request_information"
    PROGRESS = "progress"
    CLOSE = "close"
    PROVIDE_INFORMATION = "provide_information"
    WITHDRAW = "withdraw"
    SEND_TO_ALLOCATION = "send_to_allocation"
    RETURN_TO_TRIAGE = "return_to_triage"
    HOLD = "hold"
    RESUME = "resume"
    ALLOCATE = "allocate"
    RETURN_TO_COORDINATION = "return_to_coordination"
    ASSIGN = "assign"
    RETURN_FOR_REALLOCATION = "return_for_reallocation"
    SUBMIT = "submit"
    REQUEST_CLARIFICATION = "request_clarification"
    PROVIDE_CLARIFICATION = "provide_clarification"
    APPROVE = "approve"
    CHANGES_REQUIRED = "changes_required"
    RELEASE = "release"


class DeliveryTeamId(StrEnum):
    """Stable process-safe delivery-team identifiers."""

    DELIVERY_TEAM_A = "DELIVERY_TEAM_A"
    DELIVERY_TEAM_B = "DELIVERY_TEAM_B"


class WorkflowTaskState(StrEnum):
    """Camunda user-task states relevant to adapter response validation."""

    CREATING = "CREATING"
    CREATED = "CREATED"
    ASSIGNING = "ASSIGNING"
    UPDATING = "UPDATING"
    COMPLETING = "COMPLETING"
    COMPLETED = "COMPLETED"
    CANCELING = "CANCELING"
    CANCELED = "CANCELED"
    FAILED = "FAILED"


class WorkflowProcessState(StrEnum):
    """Engine process states required for terminal command recovery."""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


@dataclass(frozen=True, slots=True)
class ProcessStateQuery:
    """Exact process-instance identity for a state lookup."""

    process_instance_key: str

    def __post_init__(self) -> None:
        if not self.process_instance_key.strip():
            raise ValueError("process_instance_key must not be empty")


@dataclass(frozen=True, slots=True)
class WorkflowProcessSnapshot:
    """Minimal process evidence used to recover a terminal command."""

    process_instance_key: str
    state: WorkflowProcessState

    def __post_init__(self) -> None:
        if not self.process_instance_key.strip():
            raise ValueError("process_instance_key must not be empty")
        if not isinstance(self.state, WorkflowProcessState):
            raise TypeError("state must be a WorkflowProcessState")


@dataclass(frozen=True, slots=True)
class StartProcessCommand:
    """Start one request process without accepting arbitrary workflow variables."""

    process_definition_id: str
    request_id: UUID
    requester_id: UUID
    process_definition_version: int = -1
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        if not self.process_definition_id.strip():
            raise ValueError("process_definition_id must not be empty")
        if not isinstance(self.request_id, UUID):
            raise TypeError("request_id must be a UUID")
        if not isinstance(self.requester_id, UUID):
            raise TypeError("requester_id must be a UUID")
        if (
            self.process_definition_version != -1
            and self.process_definition_version < 1
        ):
            raise ValueError("process_definition_version must be -1 or positive")
        if self.tenant_id is not None and not self.tenant_id.strip():
            raise ValueError("tenant_id must not be empty when provided")


@dataclass(frozen=True, slots=True)
class StartedProcess:
    """Stable identifiers returned after a process starts."""

    process_instance_key: str
    process_definition_key: str
    process_definition_id: str
    process_definition_version: int
    business_id: str

    def __post_init__(self) -> None:
        values = (
            self.process_instance_key,
            self.process_definition_key,
            self.process_definition_id,
            self.business_id,
        )
        if any(not value.strip() for value in values):
            raise ValueError("started process identifiers must not be empty")
        if self.process_definition_version < 1:
            raise ValueError("started process version must be positive")


@dataclass(frozen=True, slots=True)
class StartedProcessQuery:
    """Exact business-ID lookup used to recover a successful process start."""

    process_definition_id: str
    request_id: UUID
    process_definition_version: int = -1
    tenant_id: str | None = None

    @classmethod
    def from_start(cls, command: StartProcessCommand) -> StartedProcessQuery:
        return cls(
            process_definition_id=command.process_definition_id,
            request_id=command.request_id,
            process_definition_version=command.process_definition_version,
            tenant_id=command.tenant_id,
        )

    def __post_init__(self) -> None:
        if not self.process_definition_id.strip():
            raise ValueError("process_definition_id must not be empty")
        if not isinstance(self.request_id, UUID):
            raise TypeError("request_id must be a UUID")
        if (
            self.process_definition_version != -1
            and self.process_definition_version < 1
        ):
            raise ValueError("process_definition_version must be -1 or positive")
        if self.tenant_id is not None and not self.tenant_id.strip():
            raise ValueError("tenant_id must not be empty when provided")


@dataclass(frozen=True, slots=True)
class ActiveTaskQuery:
    """Constrained search for an active task in one process instance."""

    process_instance_key: str
    expected_element_id: str | None = None

    def __post_init__(self) -> None:
        if not self.process_instance_key.strip():
            raise ValueError("process_instance_key must not be empty")
        if (
            self.expected_element_id is not None
            and not self.expected_element_id.strip()
        ):
            raise ValueError("expected_element_id must not be empty when provided")


@dataclass(frozen=True, slots=True)
class WorkflowTask:
    """Minimal user-task identity required by the application boundary."""

    task_key: str
    process_instance_key: str
    element_id: str
    state: WorkflowTaskState
    assignee: str | None = None

    def __post_init__(self) -> None:
        identifiers = (self.task_key, self.process_instance_key, self.element_id)
        if any(not value.strip() for value in identifiers):
            raise ValueError("workflow task identifiers must not be empty")
        if not isinstance(self.state, WorkflowTaskState):
            raise TypeError("state must be a WorkflowTaskState")
        if self.assignee is not None and not self.assignee.strip():
            raise ValueError("assignee must not be empty when provided")


@dataclass(frozen=True, slots=True)
class WorkflowRouteSelection:
    unit_id: UUID
    unit_code: str
    candidate_groups: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.unit_code.strip() or not self.candidate_groups:
            raise ValueError("workflow route selection must not be empty")
        if any(not group.strip() for group in self.candidate_groups):
            raise ValueError("workflow candidate groups must not be empty")


@dataclass(frozen=True, slots=True)
class CompleteTaskCommand:
    """Complete the exact expected task with one enumerated route result."""

    task_key: str
    process_instance_key: str
    expected_element_id: str
    action: WorkflowAction
    delivery_team_id: DeliveryTeamId | None = None
    specialist_id: UUID | None = None
    route_selection: WorkflowRouteSelection | None = None

    def __post_init__(self) -> None:
        if not self.task_key.strip():
            raise ValueError("task_key must not be empty")
        if not self.process_instance_key.strip():
            raise ValueError("process_instance_key must not be empty")
        if not self.expected_element_id.strip():
            raise ValueError("expected_element_id must not be empty")
        if not isinstance(self.action, WorkflowAction):
            raise TypeError("action must be a WorkflowAction")
        if self.delivery_team_id is not None and not isinstance(
            self.delivery_team_id, DeliveryTeamId
        ):
            raise TypeError("delivery_team_id must be a DeliveryTeamId")
        if self.specialist_id is not None and not isinstance(self.specialist_id, UUID):
            raise TypeError("specialist_id must be a UUID")
        if self.route_selection is not None and not isinstance(
            self.route_selection, WorkflowRouteSelection
        ):
            raise TypeError("route_selection must be a WorkflowRouteSelection")
        if self.action is WorkflowAction.ALLOCATE:
            if (self.delivery_team_id is None) == (
                self.route_selection is None
            ) or self.specialist_id is not None:
                raise ValueError("allocate requires one team route")
        elif self.action is WorkflowAction.ASSIGN:
            if (
                self.specialist_id is None
                or self.delivery_team_id is not None
                or self.route_selection is not None
            ):
                raise ValueError("assign requires only specialist_id")
        elif self.delivery_team_id is not None or self.specialist_id is not None:
            raise ValueError("routing identifiers are not valid for this action")
        if self.route_selection is not None:
            expected_groups = 2 if self.action is WorkflowAction.ALLOCATE else 1
            if (
                self.action
                not in {
                    WorkflowAction.PROGRESS,
                    WorkflowAction.SEND_TO_ALLOCATION,
                    WorkflowAction.ALLOCATE,
                }
                or len(self.route_selection.candidate_groups) != expected_groups
            ):
                raise ValueError("route selection does not match the action")


@dataclass(frozen=True, slots=True)
class ClaimTaskCommand:
    """Atomically claim an unassigned task for one application user."""

    task_key: str
    assignee_id: UUID

    def __post_init__(self) -> None:
        if not self.task_key.strip():
            raise ValueError("task_key must not be empty")
        if not isinstance(self.assignee_id, UUID):
            raise TypeError("assignee_id must be a UUID")
