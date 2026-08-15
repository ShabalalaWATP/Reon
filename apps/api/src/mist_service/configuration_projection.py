"""Deterministic current/as-of views and configuration impact previews."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from mist_service.configuration_types import (
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
                at,
            )
        )

    for unit_id, unit in next_units.items():
        previous = previous_units.get(unit_id)
        if previous is None:
            changes.append(
                _change(PreviewChangeType.ADDED, unit, "Organisation unit added.", at)
            )
        else:
            if previous.name != unit.name:
                changes.append(
                    _change(
                        PreviewChangeType.RENAMED,
                        unit,
                        f"Renamed from {previous.name} to {unit.name}.",
                        at,
                    )
                )
            if previous_parents.get(unit_id) != next_parents.get(unit_id):
                changes.append(
                    _change(
                        PreviewChangeType.MOVED,
                        unit,
                        _parent_change_message(
                            previous_units,
                            next_units,
                            previous_parents.get(unit_id),
                            next_parents.get(unit_id),
                        ),
                        at,
                    )
                )
            if previous.routing_enabled and not unit.routing_enabled:
                changes.append(
                    _change(
                        PreviewChangeType.RETIRED,
                        unit,
                        "Unit retired from new routing.",
                        at,
                    )
                )
            if previous_groups.get(unit_id) != next_groups.get(unit_id):
                changes.append(
                    _change(
                        PreviewChangeType.PERMISSION_AFFECTED,
                        unit,
                        "Candidate-group access mapping changed.",
                        at,
                    )
                )
        count = staffing.get(unit_id, StaffingCount())
        staffing_requirement_changed = previous is None or (
            not previous.routing_enabled
            or previous.minimum_managers != unit.minimum_managers
            or previous.minimum_analysts != unit.minimum_analysts
        )
        if (
            unit.routing_enabled
            and staffing_requirement_changed
            and (
                count.managers < unit.minimum_managers
                or count.analysts < unit.minimum_analysts
            )
        ):
            changes.append(
                _change(
                    PreviewChangeType.UNSTAFFED,
                    unit,
                    "Selectable team is below its configured staffing requirement.",
                    at,
                )
            )

    for unit_id, previous in previous_units.items():
        if unit_id not in next_units:
            changes.append(
                _change(
                    PreviewChangeType.RETIRED,
                    previous,
                    "Unit no longer has an effective revision for new routing.",
                    at,
                )
            )
    return sorted(
        changes, key=lambda item: (item.type.value, item.code, str(item.unit_id))
    )


def preview_configuration_schedule(
    current: ConfigurationDraftSpec | None,
    candidate: ConfigurationDraftSpec,
    *,
    starts_at: datetime,
    staffing: Mapping[UUID, StaffingCount],
) -> list[PreviewChange]:
    checkpoints = {starts_at}
    for specification in (current, candidate):
        if specification is None:
            continue
        for unit in specification.units:
            if unit.effective_from >= starts_at:
                checkpoints.add(unit.effective_from)
            if unit.effective_until is not None and unit.effective_until >= starts_at:
                checkpoints.add(unit.effective_until)
        for edge in specification.edges:
            if edge.effective_from >= starts_at:
                checkpoints.add(edge.effective_from)
            if edge.effective_until is not None and edge.effective_until >= starts_at:
                checkpoints.add(edge.effective_until)
    changes: list[PreviewChange] = []
    previous: dict[tuple[PreviewChangeType, UUID], PreviewChange] = {}
    for checkpoint in sorted(checkpoints):
        current_changes = {
            (change.type, change.unit_id): change
            for change in preview_configuration(
                current,
                candidate,
                at=checkpoint,
                staffing=staffing,
            )
        }
        for key, change in current_changes.items():
            earlier = previous.get(key)
            if earlier is None or (earlier.code, earlier.message) != (
                change.code,
                change.message,
            ):
                changes.append(change)
        for key, earlier in previous.items():
            if key not in current_changes:
                change_name = earlier.type.value.lower().replace("_", " ")
                unit_has_other_change = any(
                    unit_id == earlier.unit_id for _, unit_id in current_changes
                )
                outcome = (
                    "another scheduled difference now applies."
                    if unit_has_other_change
                    else "candidate matches the current configuration again."
                )
                changes.append(
                    PreviewChange(
                        PreviewChangeType.RESTORED,
                        earlier.unit_id,
                        earlier.code,
                        f"Earlier {change_name} change ends; {outcome}",
                        checkpoint,
                    )
                )
        previous = current_changes
    return changes


def _active(item: UnitRevisionSpec | HierarchyEdgeSpec, at: datetime) -> bool:
    return item.effective_from <= at and (
        item.effective_until is None or item.effective_until > at
    )


def _change(
    change_type: PreviewChangeType,
    unit: UnitRevisionSpec,
    message: str,
    effective_at: datetime,
) -> PreviewChange:
    return PreviewChange(change_type, unit.unit_id, unit.code, message, effective_at)


def _parent_change_message(
    previous_units: Mapping[UUID, UnitRevisionSpec],
    next_units: Mapping[UUID, UnitRevisionSpec],
    previous_parent_id: UUID | None,
    next_parent_id: UUID | None,
) -> str:
    previous = previous_units.get(previous_parent_id) if previous_parent_id else None
    following = next_units.get(next_parent_id) if next_parent_id else None
    return (
        f"Parent changed from {previous.code if previous else 'no parent'} "
        f"to {following.code if following else 'no parent'}."
    )


def mappings_for_unit(
    mappings: tuple[CandidateGroupSpec, ...], unit_id: UUID
) -> dict[CandidateGroupPurpose, str]:
    return {
        item.purpose: item.candidate_group
        for item in mappings
        if item.unit_id == unit_id
    }
