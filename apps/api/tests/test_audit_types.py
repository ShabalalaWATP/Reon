"""Validation tests for persisted security evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from istari_service.audit_types import (
    AdminAuditEvidence,
    validate_audit_details,
)


def test_audit_details_retain_unknown_safe_evidence_as_a_copy() -> None:
    original = {"futureEvidence": {"scores": [1, 2.5, True, None]}}

    validated = validate_audit_details(original)

    assert validated == original
    assert validated is not original
    assert validated["futureEvidence"] is not original["futureEvidence"]


def test_absent_audit_details_become_empty_evidence() -> None:
    assert validate_audit_details(None) == {}


@pytest.mark.parametrize(
    "details",
    [
        {"value": float("nan")},
        {"value": object()},
        {"": "value"},
        {"unsafe\nkey": "value"},
        {"value": "x" * 10_001},
        {"value": list(range(129))},
        {str(index): index for index in range(129)},
    ],
)
def test_audit_details_reject_unsafe_or_unbounded_values(
    details: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        validate_audit_details(details)


def test_audit_details_reject_excessive_depth() -> None:
    details: dict[str, object] = {}
    cursor = details
    for _ in range(8):
        nested: dict[str, object] = {}
        cursor["nested"] = nested
        cursor = nested

    with pytest.raises(ValueError, match="nesting depth"):
        validate_audit_details(details)


def test_audit_details_reject_excessively_nested_lists() -> None:
    value: object = "leaf"
    for _ in range(8):
        value = [value]

    with pytest.raises(ValueError, match="nesting depth"):
        validate_audit_details({"value": value})


def test_admin_audit_record_produces_stable_validated_payload() -> None:
    actor_id = uuid4()
    created_at = datetime(2026, 8, 11, 10, 30, tzinfo=UTC)
    record = AdminAuditEvidence(
        sequence=3,
        actor_id=actor_id,
        action="team_updated",
        target_type="team",
        target_id="synthetic-team",
        changed_fields=["name", "parent"],
        summary="Synthetic update.",
        created_at=created_at,
        previous_hash="a" * 64,
    )

    payload = record.canonical_payload()

    assert payload["actorId"] == str(actor_id)
    assert payload["changedFields"] == ["name", "parent"]
    assert payload["createdAt"] == "2026-08-11T10:30:00.000000+00:00"


def test_admin_audit_record_rejects_invalid_sequence() -> None:
    record = AdminAuditEvidence(
        sequence=0,
        actor_id=uuid4(),
        action="update",
        target_type="team",
        target_id="team-id",
        changed_fields=[],
        summary="Synthetic update.",
        created_at=datetime.now(UTC),
        previous_hash=None,
    )

    with pytest.raises(ValueError, match="sequence"):
        record.canonical_payload()


@pytest.mark.parametrize(
    ("action", "summary", "message"),
    [
        ("", "Synthetic update.", "action"),
        ("update", "x" * 10_001, "summary"),
    ],
)
def test_admin_audit_record_rejects_unbounded_fields(
    action: str,
    summary: str,
    message: str,
) -> None:
    record = AdminAuditEvidence(
        sequence=1,
        actor_id=uuid4(),
        action=action,
        target_type="team",
        target_id="team-id",
        changed_fields=[],
        summary=summary,
        created_at=datetime.now(UTC),
        previous_hash=None,
    )

    with pytest.raises(ValueError, match=message):
        record.canonical_payload()
