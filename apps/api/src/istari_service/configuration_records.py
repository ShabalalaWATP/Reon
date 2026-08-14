"""Persistence-independent records used by configuration application ports."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from istari_service.configuration_types import (
    ApprovalDecision,
    ConfigurationDraftSpec,
    ConfigurationStatus,
    FindingSeverity,
)


class ConfigurationVersionRecord(Protocol):
    """Lifecycle state required by configuration use cases and projections."""

    id: UUID
    sequence: int
    label: str
    status: ConfigurationStatus
    effective_from: datetime
    created_by_user_id: UUID
    based_on_version_id: UUID | None
    reason: str | None
    version: int
    validated_at: datetime | None
    submitted_at: datetime | None
    activated_at: datetime | None
    rejected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConfigurationApprovalRecord(Protocol):
    """Independent review evidence consumed by the activation policy."""

    id: UUID
    actor_user_id: UUID
    decision: ApprovalDecision
    reviewed_version: int
    snapshot_digest: str
    reason: str
    created_at: datetime


class ApprovedWorkflowRecord(Protocol):
    """Approved workflow metadata exposed by configuration administration."""

    id: UUID
    process_id: str
    process_definition_key: str
    process_version: int
    compatibility_key: str
    checksum: str
    approved_at: datetime
    is_available: bool


class ValidationFindingRecord(Protocol):
    severity: FindingSeverity
    code: str
    message: str
    path: str
    unit_id: UUID | None


class ConfigurationBundleRecord(Protocol):
    """An exact version snapshot, independent of its persistence representation."""

    version: ConfigurationVersionRecord
    findings: Sequence[ValidationFindingRecord]
    approval: ConfigurationApprovalRecord | None

    def specification(self) -> ConfigurationDraftSpec:
        """Return the immutable specification represented by this bundle."""


def stored_utc(value: datetime) -> datetime:
    """Normalise persisted timestamps from SQLite or PostgreSQL to UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
