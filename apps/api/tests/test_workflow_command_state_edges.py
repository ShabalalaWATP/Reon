"""Final-boundary command reauthorisation and assignment edge cases."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from mist_service.errors import InvalidAction
from mist_service.models import (
    ProductMode,
    RequestStatus,
    UserRole,
    WorkflowTaskStatus,
)
from mist_service.schemas.work import AssignSpecialist, ReturnToCoordination
from mist_service.work_command_types import (
    PendingWorkCommand,
    RoutingSelection,
    WorkCommandType,
)
from mist_service.workflow_command_state import (
    _validate_assignment,
    completion_engine_command,
    validated_command_state,
)


class StateSession:
    def __init__(
        self,
        rows: list[object | None],
        specialist: object | None = None,
        scalar_ids: list[list[object]] | None = None,
    ) -> None:
        self._rows = rows
        self._specialist = specialist
        self._scalar_ids = scalar_ids
        self.statements: list[object] = []

    async def scalar(self, statement: object) -> object | None:
        self.statements.append(statement)
        return self._rows.pop(0) if self._rows else True

    async def scalars(self, _statement: object) -> list[object]:
        return self._scalar_ids.pop(0) if self._scalar_ids else [uuid4()]

    async def get(self, _model: type[object], _identity: object) -> object | None:
        return self._specialist


def _state(
    *,
    status: RequestStatus = RequestStatus.TRIAGE_REVIEW,
    role: UserRole = UserRole.INTAKE_TRIAGE,
    scope: str = "Shared queue",
    assigned_team: str | None = None,
    assigned_team_id: Any = None,
    command_type: WorkCommandType = WorkCommandType.CLAIM_TASK,
    completion: Any = None,
) -> tuple[PendingWorkCommand, Any, Any, Any, Any]:
    actor_id = uuid4()
    request_id = uuid4()
    work_id = uuid4()
    process_key = "process-1"
    element_id = "triage-review"
    task_status = (
        WorkflowTaskStatus.CLAIM_PENDING
        if command_type is WorkCommandType.CLAIM_TASK
        else WorkflowTaskStatus.COMPLETION_PENDING
    )
    user = SimpleNamespace(
        id=actor_id,
        username="actor@example.test",
        display_name="Synthetic Actor",
        role=role,
        scope=scope,
        is_active=True,
    )
    request = SimpleNamespace(
        id=request_id,
        requester_id=uuid4(),
        status=status,
        assigned_delivery_team=assigned_team,
        assigned_delivery_team_id=assigned_team_id,
        assigned_specialist_id=None,
        product_mode=ProductMode.LEGACY,
        version=3,
    )
    task = SimpleNamespace(
        id=work_id,
        task_key="task-1",
        element_id=element_id,
        status=task_status,
        assignee_user_id=actor_id,
        candidate_role=role,
        expected_status=status,
        completed_at=None,
    )
    instance = SimpleNamespace(process_instance_key=process_key)
    command = PendingWorkCommand(
        outbox_id=uuid4(),
        command_type=command_type,
        work_id=work_id,
        task_key=task.task_key,
        process_instance_key=process_key,
        element_id=element_id,
        actor_id=actor_id,
        request_version=request.version,
        request_status=status,
        attempts=1,
        completion=completion,
    )
    return command, task, request, user, instance


async def test_validated_state_accepts_exact_current_claim() -> None:
    command, task, request, user, instance = _state()
    session = StateSession([task, request, user, instance])
    actor, work = await validated_command_state(  # type: ignore[arg-type]
        session, command, request.id
    )
    assert actor.id == user.id
    assert work.id == task.id
    assert work.request.version == request.version
    user_lock = str(session.statements[2].compile(dialect=postgresql.dialect()))
    assert user_lock.endswith("FOR NO KEY UPDATE")


async def test_validated_state_rejects_missing_or_out_of_scope_rows() -> None:
    command, _task, request, user, instance = _state()
    with pytest.raises(InvalidAction):
        await validated_command_state(  # type: ignore[arg-type]
            StateSession([None, request, user, instance]), command, request.id
        )

    command, task, request, user, instance = _state(
        status=RequestStatus.DELIVERY_PLANNING,
        role=UserRole.DELIVERY_TEAM_LEAD,
        scope="DELIVERY_TEAM_A",
        assigned_team="DELIVERY_TEAM_B",
    )
    with pytest.raises(InvalidAction):
        await validated_command_state(  # type: ignore[arg-type]
            StateSession([task, request, user, instance]), command, request.id
        )


async def test_validated_state_rechecks_action_permission() -> None:
    payload = ReturnToCoordination(
        action="return_to_coordination",
        reason="Synthetic reason",
    )
    command, task, request, user, instance = _state(
        command_type=WorkCommandType.COMPLETE_TASK,
        completion=payload,
    )
    with pytest.raises(InvalidAction):
        await validated_command_state(  # type: ignore[arg-type]
            StateSession([task, request, user, instance]), command, request.id
        )


@pytest.mark.parametrize("valid_specialist", [False, True])
async def test_assignment_is_reauthorised_at_dispatch(
    valid_specialist: bool,
) -> None:
    specialist_id = uuid4()
    payload = AssignSpecialist(
        action="assign",
        specialist_id=specialist_id,
        reason="The Manager selected the accountable delivery Lead.",
    )
    command, task, request, user, instance = _state(
        status=RequestStatus.DELIVERY_PLANNING,
        role=UserRole.DELIVERY_TEAM_LEAD,
        scope="DELIVERY_TEAM_A",
        assigned_team="DELIVERY_TEAM_A",
        assigned_team_id=uuid4(),
        command_type=WorkCommandType.COMPLETE_TASK,
        completion=payload,
    )
    team_id = request.assigned_delivery_team_id
    specialist = (
        SimpleNamespace(
            id=specialist_id,
            username="specialist@example.test",
            display_name="Synthetic Specialist",
            is_active=True,
            role=UserRole.DELIVERY_SPECIALIST,
            scope="DELIVERY_TEAM_A",
        )
        if valid_specialist
        else None
    )
    session = StateSession(
        [task, request, user, instance],
        specialist,
        [[team_id], [specialist_id], [specialist_id]],
    )
    if not valid_specialist:
        with pytest.raises(InvalidAction):
            await validated_command_state(  # type: ignore[arg-type]
                session, command, request.id
            )
        return

    actor, work = await validated_command_state(  # type: ignore[arg-type]
        session, command, request.id
    )
    assert actor.id == user.id
    assert work.request.assigned_delivery_team == "DELIVERY_TEAM_A"


async def test_dispatch_rejects_changed_assignment_routing() -> None:
    specialist_id = uuid4()
    payload = AssignSpecialist(
        action="assign",
        specialist_id=specialist_id,
        reason="The Manager selected the accountable delivery Lead.",
    )
    command, task, request, user, instance = _state(
        status=RequestStatus.DELIVERY_PLANNING,
        role=UserRole.DELIVERY_TEAM_LEAD,
        scope="DELIVERY_TEAM_A",
        assigned_team="DELIVERY_TEAM_A",
        assigned_team_id=uuid4(),
        command_type=WorkCommandType.COMPLETE_TASK,
        completion=payload,
    )
    command = replace(
        command,
        routing=RoutingSelection(
            unit_id=uuid4(),
            unit_code="SYNTHETIC",
            unit_name="Synthetic unit",
            position=1,
            candidate_groups=("synthetic-group",),
            staffed=True,
        ),
    )
    specialist = SimpleNamespace(
        id=specialist_id,
        username="specialist@example.test",
        display_name="Synthetic Specialist",
        is_active=True,
        role=UserRole.DELIVERY_SPECIALIST,
        scope="DELIVERY_TEAM_A",
    )
    team_id = request.assigned_delivery_team_id
    with pytest.raises(InvalidAction):
        await validated_command_state(  # type: ignore[arg-type]
            StateSession(
                [task, request, user, instance],
                specialist,
                [[team_id], [specialist_id], [specialist_id]],
            ),
            command,
            request.id,
        )


def test_completion_engine_command_requires_completion_payload() -> None:
    command, *_rest = _state(command_type=WorkCommandType.COMPLETE_TASK)
    with pytest.raises(InvalidAction):
        completion_engine_command(command)


async def test_non_assignment_completion_needs_no_participant_validation() -> None:
    payload = ReturnToCoordination(
        action="return_to_coordination",
        reason="Synthetic return reason.",
    )
    command, _task, request, _user, _instance = _state(
        command_type=WorkCommandType.COMPLETE_TASK,
        completion=payload,
    )
    await _validate_assignment(StateSession([]), request, command)  # type: ignore[arg-type]
    engine_command = completion_engine_command(command)
    assert engine_command.action.value == "return_to_coordination"
