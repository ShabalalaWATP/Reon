"""Strict managed-product and Customer release API contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from istari_service.product_types import (
    ArtefactKind,
    ArtefactLifecycle,
    PackageStatus,
    ScanResult,
)
from istari_service.schemas.common import ApiModel, StrictApiModel


class PackageCreate(StrictApiModel):
    request_id: UUID
    expected_version: int = Field(ge=1)
    idempotency_key: UUID


class ManagedArtefactCreate(StrictApiModel):
    expected_version: int = Field(ge=1)
    label: str = Field(min_length=2, max_length=160)
    filename: str = Field(min_length=5, max_length=180)
    media_type: str = Field(min_length=3, max_length=120)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)
    idempotency_key: UUID


class ExternalLinkCreate(StrictApiModel):
    expected_version: int = Field(ge=1)
    label: str = Field(min_length=2, max_length=160)
    url: str = Field(min_length=9, max_length=2_048)
    expires_at: datetime | None = None
    idempotency_key: UUID


class VersionCommand(StrictApiModel):
    expected_version: int = Field(ge=1)
    idempotency_key: UUID


class ApprovalCommand(VersionCommand):
    package_checksum: str = Field(min_length=64, max_length=64)


class DisseminationCommand(ApprovalCommand):
    external_link_attested: bool


class WithdrawalCommand(VersionCommand):
    reason: str = Field(min_length=8, max_length=500)


class UploadIntentView(ApiModel):
    id: UUID
    object_key: str
    upload_token: str
    expires_at: datetime


class ArtefactView(ApiModel):
    id: UUID
    package_id: UUID
    position: int
    kind: ArtefactKind
    lifecycle: ArtefactLifecycle
    label: str
    filename: str | None
    media_type: str | None
    size_bytes: int | None
    sha256: str | None
    version: int
    destination_domain: str | None = None
    expires_at: datetime | None = None
    scan_result: ScanResult | None = None
    scan_reason: str | None = None
    released_at: datetime | None = None


class PackageView(ApiModel):
    id: UUID
    request_id: UUID
    request_reference: str
    request_title: str
    author_display_name: str
    package_version: int
    status: PackageStatus
    package_checksum: str | None
    version: int
    artefacts: list[ArtefactView]
    manager_approved_at: datetime | None
    manager_approved_by: str | None
    disseminated_at: datetime | None
    disseminated_by: str | None
    withdrawal_reason: str | None


class ManagedArtefactIntent(ApiModel):
    package: PackageView
    artefact: ArtefactView
    upload_intent: UploadIntentView


class CustomerReleaseView(ApiModel):
    package_id: UUID
    request_id: UUID
    package_version: int
    status: PackageStatus
    released_at: datetime
    released_by: str
    artefacts: list[ArtefactView]


class UploadContentReceipt(ApiModel):
    intent_id: UUID
    size_bytes: int
    sha256: str
    uploaded_at: datetime
    package_version: int
