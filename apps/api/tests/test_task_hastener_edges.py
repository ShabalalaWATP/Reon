"""Pure task-hastener recipient-selection boundaries."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from istari_service.errors import InvalidAction
from istari_service.schemas.task_hasteners import TaskHastenerCommand
from istari_service.services.task_hastener_service import (
    _require_all_notified,
    _select_recipients,
)
from istari_service.task_hastener_ports import TaskHastenerRecipientRecord


def test_all_assigned_requires_at_least_one_active_analyst() -> None:
    command = TaskHastenerCommand(
        audience="ALL_ASSIGNED",
        message="Please confirm the current progress of this task.",
    )
    with pytest.raises(InvalidAction, match="no active assigned Analysts"):
        _select_recipients(command, [])


@pytest.mark.parametrize("message", ["㍿" * 500, "12345678  "])
def test_normalised_message_must_remain_within_length_bounds(message: str) -> None:
    with pytest.raises(ValidationError):
        TaskHastenerCommand(audience="ALL_ASSIGNED", message=message)


def test_normalised_message_at_the_upper_bound_is_accepted() -> None:
    command = TaskHastenerCommand(
        audience="ALL_ASSIGNED",
        message="㍿" * 125,
    )
    assert len(command.message) == 500


def test_every_resolved_analyst_must_receive_a_notification() -> None:
    recipient = TaskHastenerRecipientRecord(
        user_id=uuid4(),
        display_name="Synthetic Analyst",
        assignment_role="LEAD",
    )
    with pytest.raises(InvalidAction, match="Analysts changed"):
        _require_all_notified([recipient], frozenset())
