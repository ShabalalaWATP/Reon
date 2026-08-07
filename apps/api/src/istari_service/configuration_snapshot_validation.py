"""Validate every effective-dated organisation snapshot in a version."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from istari_service.configuration_policy import LEVEL_BY_KIND, ROUTE_DEPTH
from istari_service.configuration_types import (
    ConfigurationDraftSpec,
    FindingSeverity,
    HierarchyEdgeSpec,
    StaffingCount,
    UnitRevisionSpec,
    ValidationFinding,
)
from istari_service.organisation_models import OrganisationKind


def validate_snapshots(
    specification: ConfigurationDraftSpec,
    *,
    effective_from: datetime,
    staffing: Mapping[UUID, StaffingCount],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for checkpoint in _checkpoints(specification, effective_from):
        findings.extend(_validate_snapshot(specification, checkpoint, staffing))
    return findings


def _finding(
    severity: FindingSeverity,
    code: str,
    message: str,
    path: str,
    unit_id: UUID | None = None,
) -> ValidationFinding:
    return ValidationFinding(severity, code, message, path, unit_id)


def _checkpoints(
    specification: ConfigurationDraftSpec, effective_from: datetime
) -> list[datetime]:
    points = {effective_from}
    for revision in specification.units:
        if revision.effective_from >= effective_from:
            points.add(revision.effective_from)
        if (
            revision.effective_until is not None
            and revision.effective_until >= effective_from
        ):
            points.add(revision.effective_until)
    for edge in specification.edges:
        if edge.effective_from >= effective_from:
            points.add(edge.effective_from)
        if edge.effective_until is not None and edge.effective_until >= effective_from:
            points.add(edge.effective_until)
    return sorted(points)


def _active(item: UnitRevisionSpec | HierarchyEdgeSpec, at: datetime) -> bool:
    return item.effective_from <= at and (
        item.effective_until is None or item.effective_until > at
    )


def _validate_snapshot(
    specification: ConfigurationDraftSpec,
    at: datetime,
    staffing: Mapping[UUID, StaffingCount],
) -> list[ValidationFinding]:
    units = {
        revision.unit_id: revision
        for revision in specification.units
        if _active(revision, at)
    }
    edges = [edge for edge in specification.edges if _active(edge, at)]
    parents = {edge.child_unit_id: edge.parent_unit_id for edge in edges}
    enabled = {unit_id: unit for unit_id, unit in units.items() if unit.routing_enabled}
    findings = _snapshot_shape(units, enabled, parents, edges)
    findings.extend(_snapshot_cycles(enabled, parents))
    findings.extend(_snapshot_route(specification, enabled, parents))
    findings.extend(_staffing_warnings(enabled, staffing))
    return findings


def _snapshot_shape(
    units: Mapping[UUID, UnitRevisionSpec],
    enabled: Mapping[UUID, UnitRevisionSpec],
    parents: Mapping[UUID, UUID],
    edges: list[HierarchyEdgeSpec],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for edge in edges:
        if edge.parent_unit_id not in units or edge.child_unit_id not in units:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    "ORPHAN_EDGE",
                    "Hierarchy edges must reference active unit revisions.",
                    "edges",
                    edge.child_unit_id,
                )
            )
    for unit_id, unit in enabled.items():
        parent_id = parents.get(unit_id)
        if unit.kind is OrganisationKind.ROOT:
            if parent_id is not None:
                findings.append(
                    _finding(
                        FindingSeverity.ERROR,
                        "ROOT_HAS_PARENT",
                        "The root cannot have a parent.",
                        "edges",
                        unit_id,
                    )
                )
            continue
        parent = enabled.get(parent_id) if parent_id else None
        if parent is None:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    "ORPHAN_UNIT",
                    "Every routable non-root unit requires one routable parent.",
                    "edges",
                    unit_id,
                )
            )
        elif LEVEL_BY_KIND[parent.kind] + 1 != LEVEL_BY_KIND[unit.kind]:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    "SKIPPED_LEVEL",
                    "Hierarchy edges cannot skip or repeat a level.",
                    "edges",
                    unit_id,
                )
            )
    return findings


def _snapshot_cycles(
    enabled: Mapping[UUID, UnitRevisionSpec], parents: Mapping[UUID, UUID]
) -> list[ValidationFinding]:
    for start in enabled:
        seen: set[UUID] = set()
        current: UUID | None = start
        while current is not None and current in enabled:
            if current in seen:
                return [
                    _finding(
                        FindingSeverity.ERROR,
                        "HIERARCHY_CYCLE",
                        "The organisation hierarchy cannot contain a cycle.",
                        "edges",
                        current,
                    )
                ]
            seen.add(current)
            current = parents.get(current)
    return []


def _snapshot_route(
    specification: ConfigurationDraftSpec,
    enabled: Mapping[UUID, UnitRevisionSpec],
    parents: Mapping[UUID, UUID],
) -> list[ValidationFinding]:
    root_id = specification.workflow_template.organisation_root_id
    root = enabled.get(root_id)
    roots = [unit for unit in enabled.values() if unit.kind is OrganisationKind.ROOT]
    if root is None or root.kind is not OrganisationKind.ROOT or len(roots) != 1:
        return [
            _finding(
                FindingSeverity.ERROR,
                "ORGANISATION_ROOT_INVALID",
                "The template must select the one routable organisation root.",
                "workflowTemplate.organisationRootId",
                root_id,
            )
        ]
    for unit_id, unit in enabled.items():
        if unit.kind is not OrganisationKind.TEAM:
            continue
        current = unit_id
        depth = 0
        while current != root_id and current in parents and depth <= ROUTE_DEPTH:
            current = parents[current]
            depth += 1
        if current == root_id and depth == ROUTE_DEPTH:
            return []
    return [
        _finding(
            FindingSeverity.ERROR,
            "NO_COMPLETE_ROUTE",
            "At least one complete Customer-to-team route must remain selectable.",
            "units",
            root_id,
        )
    ]


def _staffing_warnings(
    enabled: Mapping[UUID, UnitRevisionSpec],
    staffing: Mapping[UUID, StaffingCount],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for unit_id, unit in enabled.items():
        if unit.kind is not OrganisationKind.TEAM:
            continue
        count = staffing.get(unit_id, StaffingCount())
        if (
            count.managers < unit.minimum_managers
            or count.analysts < unit.minimum_analysts
        ):
            findings.append(
                _finding(
                    FindingSeverity.WARNING,
                    "TEAM_AWAITING_STAFFING",
                    "This selectable team will wait at Awaiting team staffing.",
                    "units",
                    unit_id,
                )
            )
    return findings
