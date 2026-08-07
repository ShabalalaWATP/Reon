from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

import istari_service.configuration_validation as workflow_validation
from istari_service.configuration_policy import (
    CORE_REQUEST_FIELDS,
    HUMAN_TASK_OUTCOMES,
    WORKFLOW_COMPATIBILITY_KEY,
    WORKFLOW_SCHEMA_ID,
)
from istari_service.configuration_types import (
    ApprovedWorkflowSpec,
    CandidateGroupPurpose,
    CandidateGroupSpec,
    ConfigurationDraftSpec,
    FindingSeverity,
    HierarchyEdgeSpec,
    StaffingCount,
    UnitRevisionSpec,
    WorkflowTemplateSpec,
)
from istari_service.configuration_validation import validate_configuration
from istari_service.organisation_models import OrganisationKind

NOW = datetime(2026, 1, 1, tzinfo=UTC)
LATER = NOW + timedelta(days=30)
ROOT_ID, COMMAND_ID, OPS_ID, TEAM_ID = (UUID(int=value) for value in range(1, 5))
WORKFLOW_ID = UUID(int=20)


def _unit(
    unit_id: UUID,
    code: str,
    kind: OrganisationKind,
    *,
    start: datetime = NOW,
    end: datetime | None = None,
    enabled: bool = True,
    name: str | None = None,
) -> UnitRevisionSpec:
    is_team = kind is OrganisationKind.TEAM
    return UnitRevisionSpec(
        unit_id=unit_id,
        code=code,
        name=name or code.title(),
        kind=kind,
        effective_from=start,
        effective_until=end,
        routing_enabled=enabled,
        minimum_managers=1 if is_team else 0,
        minimum_analysts=1 if is_team else 0,
    )


def _template(**changes: object) -> WorkflowTemplateSpec:
    template = WorkflowTemplateSpec(
        schema_id=WORKFLOW_SCHEMA_ID,
        form_version="form-v1",
        notification_policy_version="notification-v1",
        organisation_root_id=ROOT_ID,
        route_depth=3,
        core_fields=tuple(sorted(CORE_REQUEST_FIELDS)),
        service_categories=("Research",),
        product_types=("Brief",),
        task_labels={task: task.replace("_", " ") for task in HUMAN_TASK_OUTCOMES},
        allowed_outcomes={
            task: tuple(sorted(outcomes))
            for task, outcomes in HUMAN_TASK_OUTCOMES.items()
        },
        reminder_days=(7, 3, 1),
        artefact_types=("PDF",),
        approved_link_domains=("example.org",),
        workflow_definition_id=WORKFLOW_ID,
    )
    return replace(template, **changes)


def _spec(**changes: object) -> ConfigurationDraftSpec:
    units = (
        _unit(ROOT_ID, "ROOT", OrganisationKind.ROOT),
        _unit(COMMAND_ID, "COMMAND", OrganisationKind.COMMAND),
        _unit(OPS_ID, "OPS", OrganisationKind.OPS_GROUP),
        _unit(TEAM_ID, "TEAM", OrganisationKind.TEAM),
    )
    edges = (
        HierarchyEdgeSpec(ROOT_ID, COMMAND_ID, NOW, None),
        HierarchyEdgeSpec(COMMAND_ID, OPS_ID, NOW, None),
        HierarchyEdgeSpec(OPS_ID, TEAM_ID, NOW, None),
    )
    groups = (
        CandidateGroupSpec(ROOT_ID, CandidateGroupPurpose.ROUTING, "route-root"),
        CandidateGroupSpec(COMMAND_ID, CandidateGroupPurpose.ROUTING, "route-command"),
        CandidateGroupSpec(OPS_ID, CandidateGroupPurpose.ROUTING, "route-ops"),
        CandidateGroupSpec(TEAM_ID, CandidateGroupPurpose.MANAGER, "team-managers"),
        CandidateGroupSpec(TEAM_ID, CandidateGroupPurpose.ANALYST, "team-analysts"),
    )
    specification = ConfigurationDraftSpec(units, edges, groups, _template())
    return replace(specification, **changes)


def _workflow(
    *, available: bool = True, compatibility: str = WORKFLOW_COMPATIBILITY_KEY
) -> ApprovedWorkflowSpec:
    return ApprovedWorkflowSpec(WORKFLOW_ID, compatibility, available)


def _validate(
    specification: ConfigurationDraftSpec,
    *,
    workflow: ApprovedWorkflowSpec | None = None,
    staffing: dict[UUID, StaffingCount] | None = None,
) -> list:
    return validate_configuration(
        specification,
        effective_from=NOW,
        workflow=_workflow() if workflow is None else workflow,
        staffing={TEAM_ID: StaffingCount(1, 1)} if staffing is None else staffing,
    )


def _codes(findings: list) -> set[str]:
    return {finding.code for finding in findings}


def test_valid_route_and_effective_dated_revisions_pass() -> None:
    assert _validate(_spec()) == []

    base = _spec()
    first_team = replace(base.units[-1], effective_until=LATER)
    renamed_team = replace(
        first_team, name="Renamed team", effective_from=LATER, effective_until=None
    )
    first_edge = replace(base.edges[-1], effective_until=LATER)
    next_edge = replace(first_edge, effective_from=LATER, effective_until=None)
    specification = replace(
        base,
        units=(*base.units[:-1], first_team, renamed_team),
        edges=(*base.edges[:-1], first_edge, next_edge),
    )

    assert _validate(specification) == []


def test_unstaffed_team_is_a_warning_not_an_error() -> None:
    findings = _validate(_spec(), staffing={})

    assert [(item.severity, item.code) for item in findings] == [
        (FindingSeverity.WARNING, "TEAM_AWAITING_STAFFING")
    ]


def test_workflow_allow_list_reports_every_unbounded_change() -> None:
    template = _template(
        schema_id="arbitrary-script/v1",
        core_fields=("title",),
        route_depth=4,
        task_labels={"intake_review": "Intake"},
        allowed_outcomes={"intake_review": ("auto_route",)},
        approved_link_domains=("localhost", "127.0.0.1", "-unsafe.example"),
    )
    findings = validate_configuration(
        replace(_spec(), workflow_template=template),
        effective_from=NOW,
        workflow=None,
        staffing={TEAM_ID: StaffingCount(1, 1)},
    )

    assert {
        "WORKFLOW_SCHEMA_INVALID",
        "CORE_FIELDS_INVALID",
        "ROUTE_DEPTH_INVALID",
        "HUMAN_TASKS_INVALID",
        "HUMAN_OUTCOMES_INVALID",
        "WORKFLOW_DEFINITION_UNKNOWN",
        "LINK_DOMAIN_INVALID",
    } <= _codes(findings)
    assert sum(item.code == "LINK_DOMAIN_INVALID" for item in findings) == 3


@pytest.mark.parametrize(
    ("workflow", "expected"),
    [
        (
            ApprovedWorkflowSpec(UUID(int=21), WORKFLOW_COMPATIBILITY_KEY, True),
            "WORKFLOW_DEFINITION_UNKNOWN",
        ),
        (_workflow(available=False), "WORKFLOW_DEFINITION_INCOMPATIBLE"),
        (
            _workflow(compatibility="unsafe-workflow"),
            "WORKFLOW_DEFINITION_INCOMPATIBLE",
        ),
    ],
)
def test_workflow_deployment_must_match_and_be_compatible(
    workflow: ApprovedWorkflowSpec, expected: str
) -> None:
    assert expected in _codes(_validate(_spec(), workflow=workflow))


def test_ip_address_is_rejected_even_if_domain_pattern_is_stubbed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PermissivePattern:
        @staticmethod
        def fullmatch(_value: str) -> bool:
            return True

    monkeypatch.setattr(workflow_validation, "DOMAIN_NAME", _PermissivePattern())
    assert workflow_validation._safe_domain("127.0.0.1") is False


def test_unit_history_code_and_staffing_rules_are_enforced() -> None:
    base = _spec()
    duplicate_code = _unit(UUID(int=5), "team", OrganisationKind.TEAM)
    changed_identity = replace(
        base.units[-1],
        code="TEAM_CHANGED",
        kind=OrganisationKind.OPS_GROUP,
        effective_from=NOW + timedelta(days=1),
        minimum_managers=0,
        minimum_analysts=0,
    )
    invalid_root = replace(base.units[0], minimum_managers=1)
    invalid_team = replace(base.units[-1], minimum_managers=0)
    findings = _validate(
        replace(
            base,
            units=(
                invalid_root,
                *base.units[1:-1],
                invalid_team,
                duplicate_code,
                changed_identity,
            ),
        )
    )

    assert {
        "DUPLICATE_UNIT_CODE",
        "STABLE_UNIT_CHANGED",
        "UNIT_REVISION_OVERLAP",
        "STAFFING_REQUIREMENT_INVALID",
    } <= _codes(findings)


def test_finite_overlapping_revision_and_edge_are_rejected() -> None:
    base = _spec()
    old_team = replace(base.units[-1], effective_until=LATER)
    overlapping_team = replace(
        old_team, effective_from=LATER - timedelta(days=1), effective_until=None
    )
    old_edge = replace(base.edges[-1], effective_until=LATER)
    overlapping_edge = replace(
        old_edge, effective_from=LATER - timedelta(days=1), effective_until=None
    )

    findings = _validate(
        replace(
            base,
            units=(*base.units[:-1], old_team, overlapping_team),
            edges=(*base.edges[:-1], old_edge, overlapping_edge),
        )
    )
    assert {"UNIT_REVISION_OVERLAP", "EDGE_OVERLAP"} <= _codes(findings)


def test_self_parent_orphan_edge_and_root_parent_are_rejected() -> None:
    base = _spec()
    unknown_id = UUID(int=99)
    findings = _validate(
        replace(
            base,
            edges=(
                *base.edges,
                HierarchyEdgeSpec(TEAM_ID, TEAM_ID, NOW, None),
                HierarchyEdgeSpec(unknown_id, OPS_ID, NOW, None),
                HierarchyEdgeSpec(TEAM_ID, ROOT_ID, NOW, None),
            ),
        )
    )
    assert {"SELF_PARENT", "EDGE_OVERLAP", "ORPHAN_EDGE", "ROOT_HAS_PARENT"} <= _codes(
        findings
    )


def test_missing_parent_skipped_level_and_cycle_are_detected() -> None:
    base = _spec()
    orphan = replace(base, edges=base.edges[1:])
    skipped = replace(
        base,
        edges=(*base.edges[:-1], HierarchyEdgeSpec(COMMAND_ID, TEAM_ID, NOW, None)),
    )
    cycle = replace(
        base,
        edges=(*base.edges, HierarchyEdgeSpec(COMMAND_ID, ROOT_ID, NOW, None)),
    )

    assert "ORPHAN_UNIT" in _codes(_validate(orphan))
    assert "SKIPPED_LEVEL" in _codes(_validate(skipped))
    assert "HIERARCHY_CYCLE" in _codes(_validate(cycle))


def test_candidate_group_identifiers_shape_uniqueness_and_ownership() -> None:
    base = _spec()
    unknown_id = UUID(int=88)
    groups = (
        CandidateGroupSpec(ROOT_ID, CandidateGroupPurpose.ROUTING, "camunda-root"),
        CandidateGroupSpec(COMMAND_ID, CandidateGroupPurpose.ROUTING, "shared-route"),
        CandidateGroupSpec(OPS_ID, CandidateGroupPurpose.ROUTING, "shared-route"),
        CandidateGroupSpec(TEAM_ID, CandidateGroupPurpose.MANAGER, "team-managers"),
        CandidateGroupSpec(unknown_id, CandidateGroupPurpose.ROUTING, "orphan-route"),
    )

    assert {
        "CANDIDATE_GROUP_INVALID",
        "CANDIDATE_GROUP_SHAPE",
        "CANDIDATE_GROUP_ORPHAN",
        "CANDIDATE_GROUP_DUPLICATE",
    } <= _codes(_validate(replace(base, candidate_groups=groups)))


@pytest.mark.parametrize("root_id", [UUID(int=77), COMMAND_ID])
def test_selected_root_must_be_the_single_routable_root(root_id: UUID) -> None:
    specification = _spec(workflow_template=_template(organisation_root_id=root_id))
    assert "ORGANISATION_ROOT_INVALID" in _codes(_validate(specification))


def test_multiple_roots_and_no_complete_route_are_rejected() -> None:
    base = _spec()
    second_root = _unit(UUID(int=7), "ROOT_TWO", OrganisationKind.ROOT)
    second_group = CandidateGroupSpec(
        second_root.unit_id, CandidateGroupPurpose.ROUTING, "route-root-two"
    )
    multiple_roots = replace(
        base,
        units=(*base.units, second_root),
        candidate_groups=(*base.candidate_groups, second_group),
    )
    disabled_team = replace(
        base, units=(*base.units[:-1], replace(base.units[-1], routing_enabled=False))
    )

    assert "ORGANISATION_ROOT_INVALID" in _codes(_validate(multiple_roots))
    assert "NO_COMPLETE_ROUTE" in _codes(_validate(disabled_team))
