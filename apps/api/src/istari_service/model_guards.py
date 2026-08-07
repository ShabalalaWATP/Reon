"""SQLAlchemy guards for immutable submitted content and audit records."""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, inspect

import istari_service.board_models as _board_models  # noqa: F401
import istari_service.calendar_models as _calendar_models  # noqa: F401
from istari_service.board_models import WorkPackageActivity
from istari_service.models import Feedback, RequestEvent, ServiceRequest
from istari_service.operations_models import OperationalRun
from istari_service.team_models import TeamActivityEvent


@event.listens_for(ServiceRequest, "before_update")
def _protect_form(_mapper: Any, _connection: Any, target: ServiceRequest) -> None:
    fields = (  # noqa: SIM905
        "title service_category description desired_outcome background_context "
        "required_by required_by_reason preferred_deliverable_type success_criteria "
        "requesting_business_area intended_recipients sensitivity handling_instructions"
    ).split()
    state = inspect(target)
    if any(state.attrs[field].history.has_changes() for field in fields):
        raise ValueError("submitted request form fields are immutable")


def _reject_audit_mutation(_mapper: Any, _connection: Any, _target: Any) -> None:
    raise ValueError("audit records are append-only")


for audit_type in (
    RequestEvent,
    Feedback,
    TeamActivityEvent,
    WorkPackageActivity,
    OperationalRun,
):
    event.listen(audit_type, "before_update", _reject_audit_mutation)
    event.listen(audit_type, "before_delete", _reject_audit_mutation)
