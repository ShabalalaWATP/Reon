"""Pure hierarchy helpers for authorised statistics scopes."""

from __future__ import annotations

from mist_service.errors import ObjectNotFound
from mist_service.schemas.statistics import StatisticsScope, StatisticsUnit


def selected_statistics_unit(
    scope: StatisticsScope,
    unit_id: object,
) -> StatisticsUnit:
    selected = next((unit for unit in scope.units if unit.id == unit_id), None)
    if selected is None:
        raise ObjectNotFound()
    return selected


def statistics_breadcrumb(
    scope: StatisticsScope,
    selected: StatisticsUnit,
) -> tuple[StatisticsUnit, ...]:
    by_id = {unit.id: unit for unit in scope.units}
    trail = [selected]
    while trail[-1].depth > 0:
        parent_id = trail[-1].parent_id
        if parent_id is None:
            raise ObjectNotFound()
        parent = by_id.get(parent_id)
        if parent is None:
            raise ObjectNotFound()
        trail.append(parent)
    trail.reverse()
    return tuple(trail)
