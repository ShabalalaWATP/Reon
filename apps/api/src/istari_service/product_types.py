"""Persistence-independent managed-product types and lifecycle values."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class PackageStatus(StrEnum):
    DRAFT = "DRAFT"
    REVIEW_READY = "REVIEW_READY"
    MANAGER_APPROVED = "MANAGER_APPROVED"
    DISSEMINATED = "DISSEMINATED"
    REPLACED = "REPLACED"
    WITHDRAWN = "WITHDRAWN"


class ArtefactKind(StrEnum):
    MANAGED_FILE = "MANAGED_FILE"
    EXTERNAL_LINK = "EXTERNAL_LINK"


class ArtefactLifecycle(StrEnum):
    PENDING_UPLOAD = "PENDING_UPLOAD"
    QUARANTINED = "QUARANTINED"
    CLEAN = "CLEAN"
    RELEASED = "RELEASED"
    FAILED = "FAILED"
    REPLACED = "REPLACED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


class ScanResult(StrEnum):
    CLEAN = "CLEAN"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    TIMED_OUT = "TIMED_OUT"


class AccessKind(StrEnum):
    DOWNLOAD = "DOWNLOAD"
    REDIRECT = "REDIRECT"


class AccessOutcome(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class UploadGrant:
    """Opaque single-purpose target, never a public object URL."""

    object_key: str
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class StoredObject:
    size_bytes: int
    media_type: str
    checksum: str


@dataclass(frozen=True, slots=True)
class ScanDecision:
    result: ScanResult
    scanner: str
    scanner_version: str
    reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class DownloadStream:
    chunks: AsyncIterator[bytes]
    media_type: str
    filename: str


@dataclass(frozen=True, slots=True)
class AccessAuditRecord:
    request_id: UUID | None
    package_id: UUID | None
    artefact_id: UUID | None
    target_reference: UUID
    actor_id: UUID
    kind: AccessKind
    outcome: AccessOutcome
    reason_code: str
    correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProductRequestRecord:
    id: UUID
    requester_id: UUID
    status: str
    assigned_team: str | None
    assigned_specialist_id: UUID | None
    version: int
    assigned_team_id: UUID | None = None
    participant_ids: frozenset[UUID] = frozenset()


@dataclass(frozen=True, slots=True)
class PackageRecord:
    id: UUID
    request_id: UUID
    author_user_id: UUID
    status: PackageStatus
    package_checksum: str | None
    version: int
    package_version: int


@dataclass(frozen=True, slots=True)
class ArtefactRecord:
    id: UUID
    package_id: UUID
    kind: ArtefactKind
    lifecycle: ArtefactLifecycle
    filename: str | None
    media_type: str | None
    size_bytes: int | None
    checksum: str | None
    quarantine_key: str | None
    released_key: str | None
    destination_url: str | None = None
    destination_domain: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class UploadIntentRecord:
    id: UUID
    artefact_id: UUID
    object_key: str
    expected_size_bytes: int
    expected_media_type: str
    expected_checksum: str
    expires_at: datetime
    uploaded_at: datetime | None
    consumed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ReleaseAccessRecord:
    request_id: UUID
    package_id: UUID
    artefact: ArtefactRecord
