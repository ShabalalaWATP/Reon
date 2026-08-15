"""Effective-dated hierarchy, candidate-group and staffing validation."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from itertools import pairwise
from uuid import UUID

from mist_service.configuration_policy import (
    EXPECTED_GROUPS,
)
from mist_service.configuration_snapshot_validation import validate_snapshots
from mist_service.configuration_types import (
    ConfigurationDraftSpec,
    FindingSeverity,
    HierarchyEdgeSpec,
    StaffingCount,
    UnitRevisionSpec,
    ValidationFinding,
)
from mist_service.organisation_models import OrganisationKind

GROUP_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$")
RESERVED_GROUP_PREFIXES = ("camunda-", "zeebe-", "system-")


def validate_hierarchy(
    specification: ConfigurationDraftSpec,
    *,
    effective_from: datetime,
    staffing: Mapping[UUID, StaffingCount],
) -> list[ValidationFinding]:
    findings = _validate_revisions(specification.units)
    findings.extend(_validate_edges(specification.edges))
    findings.extend(_validate_candidate_groups(specification))
    findings.extend(
        validate_snapshots(
            specification,
            effective_from=effective_from,
            staffing=staffing,
        )
    )
    return findings


def _finding(
    severity: FindingSeverity,
    code: str,
    message: str,
    path: str,
    unit_id: UUID | None = None,
) -> ValidationFinding:
    return ValidationFinding(severity, code, message, path, unit_id)


def _validate_revisions(
    revisions: Iterable[UnitRevisionSpec],
) -> list[ValidationFinding]:
    by_unit: dict[UUID, list[UnitRevisionSpec]] = defaultdict(list)
    code_owners: dict[str, UUID] = {}
    findings: list[ValidationFinding] = []
    for revision in revisions:
        by_unit[revision.unit_id].append(revision)
        code = revision.code.casefold()
        if code in code_owners and code_owners[code] != revision.unit_id:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    "DUPLICATE_UNIT_CODE",
                    "Stable organisation codes must be unique.",
                    "units",
                    revision.unit_id,
                )
            )
        code_owners[code] = revision.unit_id
        findings.extend(_staffing_requirement_findings(revision))
    for unit_id, history in by_unit.items():
        if (
            len({item.code for item in history}) != 1
            or len({item.kind for item in history}) != 1
        ):
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    "STABLE_UNIT_CHANGED",
                    "A stable unit identifier cannot change code or hierarchy kind.",
                    "units",
                    unit_id,
                )
            )
        findings.extend(_overlap_findings(history, unit_id, "UNIT_REVISION_OVERLAP"))
    return findings


def _staffing_requirement_findings(
    revision: UnitRevisionSpec,
) -> list[ValidationFinding]:
    if revision.kind is OrganisationKind.TEAM:
        invalid = revision.minimum_managers < 1 or revision.minimum_analysts < 1
    else:
        invalid = bool(revision.minimum_managers or revision.minimum_analysts)
    if not invalid:
        return []
    message = (
        "Delivery teams require at least one Manager and one Analyst."
        if revision.kind is OrganisationKind.TEAM
        else "Only delivery teams can define Manager or Analyst requirements."
    )
    return [
        _finding(
            FindingSeverity.ERROR,
            "STAFFING_REQUIREMENT_INVALID",
            message,
            "units",
            revision.unit_id,
        )
    ]


def _validate_edges(edges: Iterable[HierarchyEdgeSpec]) -> list[ValidationFinding]:
    by_child: dict[UUID, list[HierarchyEdgeSpec]] = defaultdict(list)
    findings: list[ValidationFinding] = []
    for edge in edges:
        by_child[edge.child_unit_id].append(edge)
        if edge.parent_unit_id == edge.child_unit_id:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    "SELF_PARENT",
                    "An organisation unit cannot parent itself.",
                    "edges",
                    edge.child_unit_id,
                )
            )
    for child_id, history in by_child.items():
        findings.extend(_overlap_findings(history, child_id, "EDGE_OVERLAP"))
    return findings


def _overlap_findings(
    records: Iterable[UnitRevisionSpec | HierarchyEdgeSpec],
    unit_id: UUID,
    code: str,
) -> list[ValidationFinding]:
    ordered = sorted(records, key=lambda item: item.effective_from)
    for previous, current in pairwise(ordered):
        if (
            previous.effective_until is None
            or current.effective_from < previous.effective_until
        ):
            return [
                _finding(
                    FindingSeverity.ERROR,
                    code,
                    "Effective-dated records for a unit cannot overlap.",
                    "units" if code.startswith("UNIT") else "edges",
                    unit_id,
                )
            ]
    return []


def _validate_candidate_groups(
    specification: ConfigurationDraftSpec,
) -> list[ValidationFinding]:
    kinds = {revision.unit_id: revision.kind for revision in specification.units}
    supplied: dict[UUID, set[object]] = defaultdict(set)
    names: Counter[str] = Counter()
    findings: list[ValidationFinding] = []
    for mapping in specification.candidate_groups:
        supplied[mapping.unit_id].add(mapping.purpose)
        names[mapping.candidate_group] += 1
        if not GROUP_NAME.fullmatch(
            mapping.candidate_group
        ) or mapping.candidate_group.startswith(RESERVED_GROUP_PREFIXES):
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    "CANDIDATE_GROUP_INVALID",
                    "Candidate groups must use a bounded non-reserved identifier.",
                    "candidateGroups",
                    mapping.unit_id,
                )
            )
    for unit_id, kind in kinds.items():
        if supplied.get(unit_id, set()) != EXPECTED_GROUPS[kind]:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    "CANDIDATE_GROUP_SHAPE",
                    "Candidate-group purposes do not match the organisation level.",
                    "candidateGroups",
                    unit_id,
                )
            )
    for unit_id in set(supplied) - set(kinds):
        findings.append(
            _finding(
                FindingSeverity.ERROR,
                "CANDIDATE_GROUP_ORPHAN",
                "A candidate group references an unknown organisation unit.",
                "candidateGroups",
                unit_id,
            )
        )
    for mapping in specification.candidate_groups:
        if names[mapping.candidate_group] > 1:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    "CANDIDATE_GROUP_DUPLICATE",
                    "Candidate groups cannot grant access to multiple unit purposes.",
                    "candidateGroups",
                    mapping.unit_id,
                )
            )
    return findings
