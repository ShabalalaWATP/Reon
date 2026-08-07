"""Deterministic current/as-of views and configuration impact previews."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from istari_service.configuration_types import (
    CandidateGroupPurpose,
    CandidateGroupSpec,
    ConfigurationDraftSpec,
    HierarchyEdgeSpec,
    PreviewChange,
    PreviewChangeType,
    StaffingCount,
    UnitRevisionSpec,
)


def active_units(
    specification: ConfigurationDraftSpec, at: datetime
) -> dict[UUID, UnitRevisionSpec]:
    return {
        revision.unit_id: revision
        for revision in specification.units
        if _active(revision, at)
    }


def active_parents(
    specification: ConfigurationDraftSpec, at: datetime
) -> dict[UUID, UUID]:
    return {
        edge.child_unit_id: edge.parent_unit_id
        for edge in specification.edges
        if _active(edge, at)
    }


def candidate_groups(
    specification: ConfigurationDraftSpec,
) -> dict[UUID, dict[CandidateGroupPurpose, str]]:
    grouped: dict[UUID, dict[CandidateGroupPurpose, str]] = defaultdict(dict)
    for item in specification.candidate_groups:
        grouped[item.unit_id][item.purpose] = item.candidate_group
    return dict(grouped)


def preview_configuration(
    current: ConfigurationDraftSpec | None,
    candidate: ConfigurationDraftSpec,
    *,
    at: datetime,
    staffing: Mapping[UUID, StaffingCount],
) -> list[PreviewChange]:
    previous_units = active_units(current, at) if current else {}
    previous_parents = active_parents(current, at) if current else {}
    previous_groups = candidate_groups(current) if current else {}
    next_units = active_units(candidate, at)
    next_parents = active_parents(candidate, at)
    next_groups = candidate_groups(candidate)
    changes: list[PreviewChange] = []

    if (
        current is not None
        and current.workflow_template != candidate.workflow_template
        and (root := next_units.get(candidate.workflow_template.organisation_root_id))
        is not None
    ):
        changes.append(
            _change(
                PreviewChangeType.WORKFLOW_AFFECTED,
                root,
                "Bounded workflow, form or catalogue configuration changed.",
            )
        )

    for unit_id, unit in next_units.items():
        previous = previous_units.get(unit_id)
        if previous is None:
            changes.append(
                _change(PreviewChangeType.ADDED, unit, "Organisation unit added.")
            )
        else:
            if previous.name != unit.name:
                changes.append(
                    _change(
                        PreviewChangeType.RENAMED,
                        unit,
                        f"Renamed from {previous.name} to {unit.name}.",
                    )
                )
            if previous_parents.get(unit_id) != next_parents.get(unit_id):
                changes.append(
                    _change(
                        PreviewChangeType.MOVED,
                        unit,
                        "Organisation parent changed.",
                    )
                )
            if previous.routing_enabled and not unit.routing_enabled:
                changes.append(
                    _change(
                        PreviewChangeType.RETIRED,
                        unit,
                        "Unit retired from new routing.",
                    )
                )
            if previous_groups.get(unit_id) != next_groups.get(unit_id):
                changes.append(
                    _change(
                        PreviewChangeType.PERMISSION_AFFECTED,
                        unit,
                        "Candidate-group access mapping changed.",
                    )
                )
        count = staffing.get(unit_id, StaffingCount())
        if unit.routing_enabled and (
            count.managers < unit.minimum_managers
            or count.analysts < unit.minimum_analysts
        ):
            changes.append(
                _change(
                    PreviewChangeType.UNSTAFFED,
                    unit,
                    "Selectable team is below its configured staffing requirement.",
                )
            )

    for unit_id, previous in previous_units.items():
        if unit_id not in next_units:
            changes.append(
                _change(
                    PreviewChangeType.RETIRED,
                    previous,
                    "Unit no longer has an effective revision for new routing.",
                )
            )
    return sorted(
        changes, key=lambda item: (item.type.value, item.code, str(item.unit_id))
    )


def _active(item: UnitRevisionSpec | HierarchyEdgeSpec, at: datetime) -> bool:
    return item.effective_from <= at and (
        item.effective_until is None or item.effective_until > at
    )


def _change(
    change_type: PreviewChangeType,
    unit: UnitRevisionSpec,
    message: str,
) -> PreviewChange:
    return PreviewChange(change_type, unit.unit_id, unit.code, message)


def mappings_for_unit(
    mappings: tuple[CandidateGroupSpec, ...], unit_id: UUID
) -> dict[CandidateGroupPurpose, str]:
    return {
        item.purpose: item.candidate_group
        for item in mappings
        if item.unit_id == unit_id
    }
