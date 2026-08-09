from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone, tzinfo
from types import MappingProxyType
from uuid import UUID

import pytest
from pydantic import ValidationError

import istari_service.configuration_policy as policy
import istari_service.configuration_projection as projection
import istari_service.schemas.configuration as schemas
from istari_service.configuration_types import (
    CandidateGroupPurpose,
    CandidateGroupSpec,
    ConfigurationStatus,
    HierarchyEdgeSpec,
    PreviewChangeType,
    StaffingCount,
)
from istari_service.models import UserRole
from istari_service.organisation_models import OrganisationKind
from test_configuration_validation import (
    COMMAND_ID,
    LATER,
    NOW,
    OPS_ID,
    ROOT_ID,
    TEAM_ID,
    _spec,
    _template,
    _unit,
)


def _workflow_values() -> dict[str, object]:
    template = _template()
    return {
        "schema_id": template.schema_id,
        "form_version": template.form_version,
        "notification_policy_version": template.notification_policy_version,
        "organisation_root_id": template.organisation_root_id,
        "route_depth": template.route_depth,
        "core_fields": list(template.core_fields),
        "service_categories": list(template.service_categories),
        "product_types": list(template.product_types),
        "task_labels": dict(template.task_labels),
        "allowed_outcomes": {
            key: list(values) for key, values in template.allowed_outcomes.items()
        },
        "reminder_days": list(template.reminder_days),
        "artefact_types": list(template.artefact_types),
        "approved_link_domains": list(template.approved_link_domains),
        "workflow_definition_id": template.workflow_definition_id,
    }


def _draft_values() -> dict[str, object]:
    specification = _spec()
    return {
        "label": "Configuration one",
        "effective_from": NOW,
        "based_on_version_id": None,
        "units": list(specification.units),
        "edges": list(specification.edges),
        "candidate_groups": list(specification.candidate_groups),
        "workflow_template": _workflow_values(),
    }


def test_lifecycle_policy_is_closed_to_platform_admin_and_valid_states() -> None:
    actor = UUID(int=501)
    assert policy.can_administer_configuration(UserRole.PLATFORM_ADMIN)
    assert not policy.can_administer_configuration(UserRole.REQUESTER)
    assert policy.actor_is_independent(actor, UUID(int=502))
    assert not policy.actor_is_independent(actor, actor)

    expected = {
        ConfigurationStatus.DRAFT: (True, True, False, False, False),
        ConfigurationStatus.VALIDATED: (False, True, True, False, False),
        ConfigurationStatus.AWAITING_APPROVAL: (False, False, False, True, True),
        ConfigurationStatus.ACTIVE: (False, False, False, False, False),
        ConfigurationStatus.SUPERSEDED: (False, False, False, False, False),
        ConfigurationStatus.REJECTED: (False, False, False, False, False),
    }
    for status, result in expected.items():
        assert (
            policy.may_replace_draft(status),
            policy.may_validate(status),
            policy.may_submit(status),
            policy.may_review(status),
            policy.may_activate(status),
        ) == result


def test_effective_dated_projection_uses_half_open_windows() -> None:
    base = _spec()
    old_team = replace(base.units[-1], effective_until=LATER)
    next_team = replace(
        old_team,
        name="Future team",
        effective_from=LATER,
        effective_until=None,
    )
    expired = _unit(
        UUID(int=91),
        "OLD_TEAM",
        OrganisationKind.TEAM,
        start=NOW - timedelta(days=2),
        end=NOW,
    )
    old_edge = replace(base.edges[-1], effective_until=LATER)
    next_edge = HierarchyEdgeSpec(COMMAND_ID, TEAM_ID, LATER, None)
    specification = replace(
        base,
        units=(*base.units[:-1], old_team, next_team, expired),
        edges=(*base.edges[:-1], old_edge, next_edge),
    )

    assert projection.active_units(specification, NOW)[TEAM_ID].name == "Team"
    assert UUID(int=91) not in projection.active_units(specification, NOW)
    assert projection.active_units(specification, LATER)[TEAM_ID].name == "Future team"
    assert projection.active_parents(specification, NOW)[TEAM_ID] == OPS_ID
    assert projection.active_parents(specification, LATER)[TEAM_ID] == COMMAND_ID


def test_candidate_group_projection_and_unit_filtering() -> None:
    mappings = (
        CandidateGroupSpec(ROOT_ID, CandidateGroupPurpose.ROUTING, "route-old"),
        CandidateGroupSpec(ROOT_ID, CandidateGroupPurpose.ROUTING, "route-new"),
    )
    specification = replace(_spec(), candidate_groups=mappings)

    assert projection.candidate_groups(specification)[ROOT_ID] == {
        CandidateGroupPurpose.ROUTING: "route-new"
    }
    assert projection.mappings_for_unit(mappings, ROOT_ID) == {
        CandidateGroupPurpose.ROUTING: "route-new"
    }
    assert projection.mappings_for_unit(mappings, UUID(int=404)) == {}


def test_preview_reports_every_bounded_change_in_stable_order() -> None:
    current = _spec()
    new_team_id = UUID(int=8)
    candidate = replace(
        current,
        workflow_template=replace(current.workflow_template, form_version="form-v2"),
        units=(
            replace(current.units[0], name="Renamed root"),
            replace(current.units[2], name="Ops"),
            replace(current.units[3], routing_enabled=False),
            _unit(new_team_id, "TEAM_NEW", OrganisationKind.TEAM),
        ),
        edges=(
            HierarchyEdgeSpec(ROOT_ID, OPS_ID, NOW, None),
            current.edges[2],
            HierarchyEdgeSpec(OPS_ID, new_team_id, NOW, None),
        ),
        candidate_groups=(
            CandidateGroupSpec(ROOT_ID, CandidateGroupPurpose.ROUTING, "route-new"),
            *current.candidate_groups[2:],
            CandidateGroupSpec(
                new_team_id, CandidateGroupPurpose.MANAGER, "new-team-managers"
            ),
            CandidateGroupSpec(
                new_team_id, CandidateGroupPurpose.ANALYST, "new-team-analysts"
            ),
        ),
    )

    changes = projection.preview_configuration(current, candidate, at=NOW, staffing={})
    assert {item.type for item in changes} == set(PreviewChangeType) - {
        PreviewChangeType.RESTORED
    }
    assert changes == sorted(
        changes, key=lambda item: (item.type.value, item.code, str(item.unit_id))
    )
    assert all(item.message for item in changes)

    initial = projection.preview_configuration(
        None,
        current,
        at=NOW,
        staffing={TEAM_ID: StaffingCount(managers=1, analysts=1)},
    )
    assert [item.type for item in initial] == [PreviewChangeType.ADDED] * 4


def test_draft_schema_normalises_aliases_and_converts_to_immutable_spec() -> None:
    values = _draft_values()
    values["effective_from"] = datetime(
        2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1))
    )
    workflow = values["workflow_template"]
    assert isinstance(workflow, dict)
    workflow["service_categories"] = ["  Research  "]
    workflow["product_types"] = ["  Brief  "]
    workflow["task_labels"] = {
        task: f"  {task.replace('_', ' ')}  " for task in policy.HUMAN_TASK_OUTCOMES
    }
    workflow["reminder_days"] = [7, 1, 3]
    workflow["approved_link_domains"] = ["EXAMPLE.ORG."]

    command = schemas.ConfigurationDraftCreate.model_validate(values)
    specification = command.to_spec()
    dumped = command.model_dump(by_alias=True)

    assert command.effective_from == NOW
    assert command.workflow_template.service_categories == ["Research"]
    assert command.workflow_template.reminder_days == [1, 3, 7]
    assert command.workflow_template.approved_link_domains == ["example.org"]
    assert isinstance(specification.workflow_template.task_labels, MappingProxyType)
    assert specification.workflow_template.core_fields == tuple(
        sorted(policy.CORE_REQUEST_FIELDS)
    )
    assert "effectiveFrom" in dumped and "workflowTemplate" in dumped


class _MissingOffset(tzinfo):
    def utcoffset(self, _dt: datetime | None) -> None:
        return None

    def dst(self, _dt: datetime | None) -> None:
        return None

    def tzname(self, _dt: datetime | None) -> str:
        return "missing"


NAIVE = NOW.replace(tzinfo=None)


@pytest.mark.parametrize(
    "updates",
    [
        {"effective_from": NAIVE},
        {"effective_from": datetime(2026, 1, 1, tzinfo=_MissingOffset())},
        {"effective_until": NOW},
        {"code": "lower-case"},
        {"name": "  x  "},
        {"name": "Safe\u202eName"},
        {"minimum_managers": -1},
    ],
)
def test_unit_revision_rejects_invalid_boundaries(updates: dict[str, object]) -> None:
    values = _draft_values()["units"]
    assert isinstance(values, list)
    baseline = schemas.UnitRevisionInput.model_validate(values[0]).model_dump()
    with pytest.raises(ValidationError):
        schemas.UnitRevisionInput.model_validate({**baseline, **updates})


@pytest.mark.parametrize(
    "updates",
    [
        {"parent_unit_id": COMMAND_ID},
        {"effective_from": NAIVE},
        {"effective_until": NOW},
    ],
)
def test_hierarchy_edge_rejects_self_parent_and_invalid_times(
    updates: dict[str, object],
) -> None:
    values = _draft_values()["edges"]
    assert isinstance(values, list)
    baseline = schemas.HierarchyEdgeInput.model_validate(values[0]).model_dump()
    edge = {**baseline, **updates}
    if "parent_unit_id" in updates:
        edge["child_unit_id"] = COMMAND_ID
    with pytest.raises(ValidationError):
        schemas.HierarchyEdgeInput.model_validate(edge)


@pytest.mark.parametrize("candidate_group", ["x", "UPPER-GROUP", "bad_group"])
def test_candidate_group_input_enforces_bounded_slug(candidate_group: str) -> None:
    with pytest.raises(ValidationError):
        schemas.CandidateGroupInput(
            unit_id=ROOT_ID,
            purpose=CandidateGroupPurpose.ROUTING,
            candidate_group=candidate_group,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("core_fields", ["title", "title"]),
        ("service_categories", ["Research", "Research"]),
        ("product_types", ["Brief", "Brief"]),
        ("artefact_types", ["PDF", "PDF"]),
        ("service_categories", [" "]),
        ("product_types", ["x" * 121]),
        ("reminder_days", [1, 1]),
        ("reminder_days", [-1]),
        ("reminder_days", [366]),
        ("approved_link_domains", ["Example.org", "example.org."]),
    ],
)
def test_workflow_input_rejects_duplicate_or_unbounded_lists(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        schemas.WorkflowTemplateInput.model_validate(
            {**_workflow_values(), field: value}
        )


@pytest.mark.parametrize("label", [" ", "x" * 121])
def test_workflow_input_bounds_human_task_labels(label: str) -> None:
    labels = dict(_template().task_labels)
    labels["intake_review"] = label
    with pytest.raises(ValidationError):
        schemas.WorkflowTemplateInput.model_validate(
            {**_workflow_values(), "task_labels": labels}
        )


def test_strict_schema_commands_reject_extra_fields_and_short_reasons() -> None:
    with pytest.raises(ValidationError):
        schemas.ConfigurationDraftCreate.model_validate(
            {**_draft_values(), "script": "x"}
        )
    with pytest.raises(ValidationError):
        schemas.ConfigurationDraftCreate.model_validate(
            {**_draft_values(), "effective_from": NAIVE}
        )
    with pytest.raises(ValidationError):
        schemas.ConfigurationDraftReplace.model_validate(
            {**_draft_values(), "expected_version": 0}
        )
    with pytest.raises(ValidationError):
        schemas.ConfigurationVersionCommand(expected_version=0)
    with pytest.raises(ValidationError):
        schemas.ConfigurationReasonCommand(expected_version=1, reason="too short")

    assert schemas.ConfigurationVersionCommand(expected_version=1).expected_version == 1
    assert (
        schemas.ConfigurationReasonCommand(
            expected_version=2, reason="Sufficient review reason"
        ).reason
        == "Sufficient review reason"
    )
