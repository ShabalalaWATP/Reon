"""Direct-child comparisons for an authorised statistics scope."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID

from istari_service.analytics_models import RequestAnalyticsFact
from istari_service.models import RequestStatus
from istari_service.organisation_models import OrganisationKind, OrganisationUnit
from istari_service.schemas.statistics import ChildUnitComparison

RATING_COHORT = 5
TERMINAL_STATUSES = {
    RequestStatus.COMPLETED,
    RequestStatus.CLOSED_NOT_PROGRESSED,
    RequestStatus.CANCELLED,
}


def child_comparisons(
    scope_kind: OrganisationKind | str,
    facts: tuple[RequestAnalyticsFact, ...],
    children: tuple[OrganisationUnit, ...],
    as_of_date: date,
) -> list[ChildUnitComparison]:
    attribute = {
        "PLATFORM": "command_unit_id",
        OrganisationKind.ROOT: "command_unit_id",
        OrganisationKind.COMMAND: "ops_unit_id",
        OrganisationKind.OPS_GROUP: "team_unit_id",
    }.get(scope_kind)
    if attribute is None:
        return []
    grouped: dict[UUID, list[RequestAnalyticsFact]] = defaultdict(list)
    for fact in facts:
        unit_id = getattr(fact, attribute)
        if unit_id is not None:
            grouped[unit_id].append(fact)
    return [_child_row(unit, grouped[unit.id], as_of_date) for unit in children]


def _child_row(
    unit: OrganisationUnit,
    facts: list[RequestAnalyticsFact],
    as_of_date: date,
) -> ChildUnitComparison:
    active = [fact for fact in facts if fact.current_status not in TERMINAL_STATUSES]
    ratings = [
        fact.feedback_rating for fact in facts if fact.feedback_rating is not None
    ]
    suppressed = len(ratings) < RATING_COHORT
    return ChildUnitComparison(
        unit_id=unit.id,
        name=unit.name,
        kind=unit.kind,
        received=len(facts),
        active=len(active),
        completed=sum(f.current_status is RequestStatus.COMPLETED for f in facts),
        overdue=sum(f.required_by < as_of_date for f in active),
        feedback_count=len(ratings),
        average_rating=None if suppressed else round(sum(ratings) / len(ratings), 2),
        rating_suppressed=suppressed,
    )
