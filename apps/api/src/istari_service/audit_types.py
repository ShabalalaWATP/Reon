"""Validated, framework-free records used at the audit persistence boundary."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

MAX_AUDIT_DEPTH = 6
MAX_AUDIT_ITEMS = 128
MAX_AUDIT_KEY_LENGTH = 120
MAX_AUDIT_STRING_LENGTH = 10_000

type AuditScalar = str | int | float | bool | None
type AuditValue = AuditScalar | list[AuditValue] | dict[str, AuditValue]
type AuditDetails = dict[str, AuditValue]


def validate_audit_details(
    details: Mapping[str, object] | None,
) -> AuditDetails:
    """Return a JSON-safe copy of bounded evidence, retaining unknown safe fields."""

    if details is None:
        return {}
    return _validate_mapping(details, depth=0)


def _validate_mapping(values: Mapping[str, object], *, depth: int) -> AuditDetails:
    if depth > MAX_AUDIT_DEPTH:
        raise ValueError("audit evidence exceeds the maximum nesting depth")
    if len(values) > MAX_AUDIT_ITEMS:
        raise ValueError("audit evidence contains too many fields")
    result: AuditDetails = {}
    for key, value in values.items():
        if not isinstance(key, str) or not 0 < len(key) <= MAX_AUDIT_KEY_LENGTH:
            raise ValueError("audit evidence keys must be bounded strings")
        if any(ord(character) < 32 for character in key):
            raise ValueError("audit evidence keys cannot contain control characters")
        result[key] = _validate_value(value, depth=depth + 1)
    return result


def _validate_value(value: object, *, depth: int) -> AuditValue:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("audit evidence numbers must be finite")
        return value
    if isinstance(value, str):
        if len(value) > MAX_AUDIT_STRING_LENGTH:
            raise ValueError("audit evidence strings are too long")
        return value
    if isinstance(value, Mapping):
        return _validate_mapping(value, depth=depth)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        if depth > MAX_AUDIT_DEPTH:
            raise ValueError("audit evidence exceeds the maximum nesting depth")
        if len(value) > MAX_AUDIT_ITEMS:
            raise ValueError("audit evidence contains too many list items")
        return [_validate_value(item, depth=depth + 1) for item in value]
    raise ValueError("audit evidence must contain JSON-compatible values")


@dataclass(frozen=True, slots=True)
class AuditEventEvidence:
    """One stored request event presented for integrity verification."""

    request_id: UUID
    event_type: str
    message: str
    actor_id: UUID | None
    created_at: datetime
    previous_hash: str | None
    event_hash: str
    prior_status: str | None = None
    next_status: str | None = None
    details: Mapping[str, object] | None = None

    def validated_details(self) -> AuditDetails:
        return validate_audit_details(self.details)


@dataclass(frozen=True, slots=True)
class AdminAuditEvidence:
    """Validated fields that form one administrative event hash."""

    sequence: int
    actor_id: UUID
    action: str
    target_type: str
    target_id: str
    changed_fields: Sequence[str]
    summary: str
    created_at: datetime
    previous_hash: str | None

    def canonical_payload(self) -> AuditDetails:
        if self.sequence < 1:
            raise ValueError("admin audit sequence must be positive")
        for label, value in (
            ("action", self.action),
            ("target type", self.target_type),
            ("target ID", self.target_id),
        ):
            if not 0 < len(value) <= 200:
                raise ValueError(f"admin audit {label} must be bounded")
        if len(self.summary) > MAX_AUDIT_STRING_LENGTH:
            raise ValueError("admin audit summary is too long")
        return validate_audit_details(
            {
                "action": self.action,
                "actorId": str(self.actor_id),
                "changedFields": sorted(self.changed_fields),
                "createdAt": self.created_at.isoformat(timespec="microseconds"),
                "previousHash": self.previous_hash,
                "sequence": self.sequence,
                "summary": self.summary,
                "targetId": self.target_id,
                "targetType": self.target_type,
            }
        )
