"""Immutable hand-offs between managed-product transactional phases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from mist_service.schemas.products import ManagedArtefactCreate


@dataclass(frozen=True, slots=True)
class ManagedPreparation:
    package_id: UUID
    command: ManagedArtefactCreate
    filename: str
    media_type: str
    object_key: str


@dataclass(frozen=True, slots=True)
class ContentOperation:
    package_id: UUID
    intent_id: UUID
    object_key: str
    expected_version: int
    expected_size: int
    expected_checksum: str
    token_hash: str
    owner: str | None
    generation: int | None
    uploaded_at: datetime | None
    package_version: int


@dataclass(frozen=True, slots=True)
class ScanOperation:
    package_id: UUID
    intent_id: UUID
    artefact_id: UUID
    object_key: str
    filename: str
    media_type: str
    expected_size: int
    expected_checksum: str
    expected_version: int
    idempotency_key: UUID
    owner: str
    generation: int
