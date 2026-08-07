"""Final-boundary command reauthorisation and assignment edge cases."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from istari_service.errors import InvalidAction
from istari_service.models import RequestStatus, UserRole, WorkflowTaskStatus
from istari_service.schemas.work import AssignSpecialist, ReturnToCoordination
from istari_service.work_command_types import PendingWorkCommand, WorkCommandType
from istari_service.workflow_command_state import (
    completion_engine_command,
    validated_command_state,
)


class StateSession:
    def __init__(
        self,
        rows: list[object | None],
        specialist: object | None = None,
    ) -> None:
        self._rows = rows
        self._specialist = specialist

    async def scalar(self, _statement: object) -> object | None:
        return self._rows.pop(0) if self._rows else True

    async def get(self, _model: type[object], _identity: object) -> object | None:
        return self._specialist


def _state(
    *,
    status: RequestStatus = RequestStatus.TRIAGE_REVIEW,
    role: UserRole = UserRole.INTAKE_TRIAGE,
    scope: str = "Shared queue",
    assigned_team: str | None = None,
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
        assigned_specialist_id=None,
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
    actor, work = await validated_command_state(  # type: ignore[arg-type]
        StateSession([task, request, user, instance]), command, request.id
    )
    assert actor.id == user.id
    assert work.id == task.id
    assert work.request.version == request.version


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
    payload = AssignSpecialist(action="assign", specialist_id=specialist_id)
    command, task, request, user, instance = _state(
        status=RequestStatus.DELIVERY_PLANNING,
        role=UserRole.DELIVERY_TEAM_LEAD,
        scope="DELIVERY_TEAM_A",
        assigned_team="DELIVERY_TEAM_A",
        command_type=WorkCommandType.COMPLETE_TASK,
        completion=payload,
    )
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
    session = StateSession([task, request, user, instance], specialist)
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


def test_completion_engine_command_requires_completion_payload() -> None:
    command, *_rest = _state(command_type=WorkCommandType.COMPLETE_TASK)
    with pytest.raises(InvalidAction):
        completion_engine_command(command)
