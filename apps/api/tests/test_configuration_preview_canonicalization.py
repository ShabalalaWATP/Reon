from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import pytest

from mist_service.configuration_digest import _record
from mist_service.configuration_projection import (
    preview_configuration,
    preview_configuration_schedule,
)
from mist_service.configuration_types import (
    CandidateGroupPurpose,
    CandidateGroupSpec,
    HierarchyEdgeSpec,
    PreviewChangeType,
)
from mist_service.schemas import configuration as schemas
from test_configuration_projection_schema import _draft_values
from test_configuration_validation import LATER, NOW, OPS_ID, _codes, _spec, _validate


def test_preview_canonicalises_reminders_and_reports_only_new_staffing_impact() -> None:
    current = _spec()
    reordered = replace(
        current,
        workflow_template=replace(
            current.workflow_template,
            reminder_days=tuple(reversed(current.workflow_template.reminder_days)),
        ),
    )

    assert preview_configuration(current, reordered, at=NOW, staffing={}) == []

    raised_team = replace(
        current.units[-1],
        minimum_managers=current.units[-1].minimum_managers + 1,
    )
    raised = preview_configuration(
        current,
        replace(current, units=(*current.units[:-1], raised_team)),
        at=NOW,
        staffing={},
    )
    assert [item.type for item in raised] == [PreviewChangeType.UNSTAFFED]

    reordered_workflow = replace(
        current.workflow_template,
        core_fields=tuple(reversed(current.workflow_template.core_fields)),
        artefact_types=tuple(reversed(current.workflow_template.artefact_types)),
        approved_link_domains=tuple(
            reversed(current.workflow_template.approved_link_domains)
        ),
        allowed_outcomes={
            key: tuple(reversed(values))
            for key, values in current.workflow_template.allowed_outcomes.items()
        },
    )
    assert replace(current, workflow_template=reordered_workflow) == current


def test_preview_schedule_reveals_later_effective_changes_once() -> None:
    current = _spec()
    team = current.units[-1]
    candidate = replace(
        current,
        units=(*current.units[:-1], replace(team, effective_until=LATER)),
        edges=(
            *current.edges[:-1],
            replace(current.edges[-1], effective_until=LATER),
        ),
    )

    assert preview_configuration(current, candidate, at=NOW, staffing={}) == []
    changes = preview_configuration_schedule(
        current,
        candidate,
        starts_at=NOW,
        staffing={},
    )

    assert [(item.type, item.effective_at) for item in changes] == [
        (PreviewChangeType.RETIRED, LATER)
    ]


def test_preview_schedule_reveals_when_a_temporary_change_ends() -> None:
    current = _spec()
    team = current.units[-1]
    restored_at = LATER + timedelta(days=10)
    candidate = replace(
        current,
        units=(
            *current.units[:-1],
            replace(team, effective_until=LATER),
            replace(
                team,
                name="Temporary team name",
                effective_from=LATER,
                effective_until=restored_at,
            ),
            replace(team, effective_from=restored_at),
        ),
    )

    changes = preview_configuration_schedule(
        current,
        candidate,
        starts_at=NOW,
        staffing={},
    )

    assert [(item.type, item.effective_at) for item in changes] == [
        (PreviewChangeType.RENAMED, LATER),
        (PreviewChangeType.RESTORED, restored_at),
    ]
    assert "matches the current configuration again" in changes[-1].message


def test_preview_restoration_does_not_claim_match_when_retirement_starts() -> None:
    current = _spec()
    team = current.units[-1]
    candidate = replace(
        current,
        units=(
            *current.units[:-1],
            replace(team, effective_until=LATER),
            replace(
                team,
                name="Temporary team name",
                effective_from=NOW,
                effective_until=LATER,
            ),
        ),
        edges=(
            *current.edges[:-1],
            replace(current.edges[-1], effective_until=LATER),
        ),
    )

    changes = preview_configuration_schedule(
        current,
        candidate,
        starts_at=NOW,
        staffing={},
    )

    restored = next(
        item
        for item in changes
        if item.type is PreviewChangeType.RESTORED and item.effective_at == LATER
    )
    assert "another scheduled difference now applies" in restored.message
    assert "matches the current configuration again" not in restored.message


def test_unit_revision_normalises_safe_display_names() -> None:
    values = _draft_values()["units"]
    assert isinstance(values, list)
    baseline = schemas.UnitRevisionInput.model_validate(values[0]).model_dump()
    parsed = schemas.UnitRevisionInput.model_validate(
        {**baseline, "name": "  \uff21urora Ops  "}
    )
    assert parsed.name == "Aurora Ops"


def test_effective_siblings_require_distinct_display_names() -> None:
    base = _spec()
    existing = base.units[-1]
    duplicate_id = UUID(int=55)
    duplicate = replace(existing, unit_id=duplicate_id, code="TEAM_TWO")
    specification = replace(
        base,
        units=(*base.units, duplicate),
        edges=(*base.edges, HierarchyEdgeSpec(OPS_ID, duplicate_id, NOW, None)),
        candidate_groups=(
            *base.candidate_groups,
            CandidateGroupSpec(
                duplicate_id, CandidateGroupPurpose.MANAGER, "team-two-managers"
            ),
            CandidateGroupSpec(
                duplicate_id, CandidateGroupPurpose.ANALYST, "team-two-analysts"
            ),
        ),
    )

    assert "DUPLICATE_SIBLING_NAME" in _codes(_validate(specification))


def test_configuration_digest_rejects_non_record_input() -> None:
    with pytest.raises(TypeError, match="must be dataclasses"):
        _record(object())
