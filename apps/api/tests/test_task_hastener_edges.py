"""Pure task-hastener recipient-selection boundaries."""

import pytest

from istari_service.errors import InvalidAction
from istari_service.schemas.task_hasteners import TaskHastenerCommand
from istari_service.services.task_hastener_service import _select_recipients


def test_all_assigned_requires_at_least_one_active_analyst() -> None:
    command = TaskHastenerCommand(
        audience="ALL_ASSIGNED",
        message="Please confirm the current progress of this task.",
    )
    with pytest.raises(InvalidAction, match="no active assigned Analysts"):
        _select_recipients(command, [])
