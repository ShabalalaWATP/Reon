"""Narrow application ports for managed-product persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from mist_service.domain import Actor
from mist_service.product_types import (
    ArtefactRecord,
    PackageRecord,
    ProductRequestRecord,
    ProductStorageUsage,
    ReleaseAccessRecord,
    ScanDecision,
    UploadIntentRecord,
)
from mist_service.schemas.products import CustomerReleaseView, PackageView


class ProductAccessRepository(Protocol):
    """Package and request access shared by product policy support."""

    async def active_actor(self, actor: Actor) -> bool: ...

    async def request(
        self, request_id: UUID, *, lock: bool
    ) -> ProductRequestRecord | None: ...

    async def package(
        self, package_id: UUID, *, lock: bool
    ) -> PackageRecord | None: ...

    async def live_delivery_membership(
        self,
        actor_id: UUID,
        team_id: UUID | None,
        team_name: str | None,
        *,
        manager: bool,
    ) -> bool: ...


class ProductLinkRepository(Protocol):
    """Request-pinned external-link configuration."""

    async def approved_link_domains(
        self, request_id: UUID
    ) -> frozenset[str] | None: ...


class ProductReviewTaskRepository(Protocol):
    """Accountability for the human tasks which can change a package."""

    async def manager_task_claimed_by(
        self, package_id: UUID, actor_id: UUID
    ) -> bool: ...

    async def release_task_claimed_by(
        self, package_id: UUID, actor_id: UUID
    ) -> bool: ...

    async def quality_task_claimed_by(
        self, package_id: UUID, actor_id: UUID
    ) -> bool: ...


class ProductPackageServiceRepository(ProductAccessRepository, Protocol):
    """Package authoring, inspection and approval persistence."""

    async def live_qc_membership(self, actor_id: UUID, *, manager: bool) -> bool: ...

    async def create_package(
        self, request_id: UUID, actor_id: UUID, creation_key: UUID
    ) -> PackageRecord: ...

    async def latest_package(self, request_id: UUID) -> PackageRecord | None: ...

    async def view(
        self, package_id: UUID, *, include_review_details: bool = False
    ) -> PackageView: ...

    async def package_digest(
        self, package_id: UUID, covering_note: str | None
    ) -> tuple[str, int, int]: ...

    async def freeze(
        self, package_id: UUID, checksum: str, covering_note: str | None
    ) -> PackageRecord: ...

    async def approve(
        self, package_id: UUID, actor_id: UUID, *, now: datetime
    ) -> PackageRecord: ...


class ProductReviewServiceRepository(ProductAccessRepository, Protocol):
    """Staff review access and claimed-task accountability."""

    async def live_qc_membership(self, actor_id: UUID, *, manager: bool) -> bool: ...

    async def review_access(self, artefact_id: UUID) -> ReleaseAccessRecord | None: ...

    async def manager_task_claimed_by(
        self, package_id: UUID, actor_id: UUID
    ) -> bool: ...

    async def release_task_claimed_by(
        self, package_id: UUID, actor_id: UUID
    ) -> bool: ...

    async def quality_task_claimed_by(
        self, package_id: UUID, actor_id: UUID
    ) -> bool: ...


class ProductUploadServiceRepository(ProductAccessRepository, Protocol):
    """Draft projection and external-link authoring persistence."""

    async def view(
        self, package_id: UUID, *, include_review_details: bool = False
    ) -> PackageView: ...

    async def create_external(
        self,
        package_id: UUID,
        *,
        label: str,
        destination: str,
        domain: str,
        expires_at: datetime | None,
        creation_key: UUID,
    ) -> ArtefactRecord: ...


class ProductManagedUploadRepository(Protocol):
    """Managed artefact reservation, grant and quota persistence."""

    async def storage_usage(
        self, package_id: UUID, request_id: UUID, author_id: UUID
    ) -> ProductStorageUsage: ...

    async def create_managed(
        self,
        package_id: UUID,
        *,
        label: str,
        filename: str,
        media_type: str,
        size_bytes: int,
        checksum: str,
        creation_key: UUID,
        intent_key: UUID,
        object_key: str,
        token_hash: str,
        expires_at: datetime,
    ) -> tuple[ArtefactRecord, UploadIntentRecord]: ...

    async def managed_retry(
        self, package_id: UUID, creation_key: UUID
    ) -> tuple[ArtefactRecord, UploadIntentRecord] | None: ...

    async def refresh_upload_grant(
        self,
        intent_id: UUID,
        *,
        token_hash: str,
        expires_at: datetime,
    ) -> UploadIntentRecord: ...


class ProductUploadContentRepository(Protocol):
    """Upload-intent content and scan-result persistence."""

    async def upload_intent(
        self, package_id: UUID, intent_id: UUID, *, lock: bool
    ) -> tuple[ArtefactRecord, UploadIntentRecord] | None: ...

    async def upload_token_hash(self, intent_id: UUID) -> str | None: ...

    async def mark_uploaded(self, intent_id: UUID, *, now: datetime) -> None: ...

    async def record_scan(
        self,
        artefact_id: UUID,
        idempotency_key: UUID,
        decision: ScanDecision,
        checksum: str,
        released_key: str | None,
    ) -> ArtefactRecord: ...


class ProductTransferRepository(ProductAccessRepository, Protocol):
    """Package access and projection for detached transfer phases."""

    async def view(
        self, package_id: UUID, *, include_review_details: bool = False
    ) -> PackageView: ...


class ProductOperationLeaseRepository(Protocol):
    """Exclusive short-lived ownership for detached transfer phases."""

    async def claim_intent_operation(
        self,
        intent_id: UUID,
        *,
        owner: str,
        now: datetime,
        expires_at: datetime,
    ) -> int: ...

    async def require_intent_operation(
        self,
        intent_id: UUID,
        *,
        owner: str,
        generation: int,
    ) -> None: ...

    async def release_intent_operation(
        self,
        intent_id: UUID,
        *,
        owner: str,
        generation: int,
    ) -> bool: ...


class ProductReleaseServiceRepository(ProductAccessRepository, Protocol):
    """QC release and withdrawal persistence."""

    async def live_qc_membership(self, actor_id: UUID, *, manager: bool) -> bool: ...

    async def latest_package(self, request_id: UUID) -> PackageRecord | None: ...

    async def view(
        self, package_id: UUID, *, include_review_details: bool = False
    ) -> PackageView: ...

    async def attest_links(
        self, package_id: UUID, actor_id: UUID, *, now: datetime
    ) -> None: ...

    async def disseminate(
        self,
        package_id: UUID,
        actor_id: UUID,
        recipient_id: UUID,
        idempotency_key: UUID,
        *,
        now: datetime,
    ) -> PackageRecord: ...

    async def dissemination_matches(
        self, package_id: UUID, recipient_id: UUID, idempotency_key: UUID
    ) -> bool: ...

    async def release_excluded_actor_ids(self, package_id: UUID) -> frozenset[UUID]: ...

    async def withdraw(
        self,
        package_id: UUID,
        actor_id: UUID,
        reason: str,
        *,
        now: datetime,
    ) -> PackageRecord: ...


class ProductCustomerReleaseRepository(Protocol):
    """Customer release projection, acceptance and artefact access."""

    async def active_actor(self, actor: Actor) -> bool: ...

    async def request(
        self, request_id: UUID, *, lock: bool
    ) -> ProductRequestRecord | None: ...

    async def release_view(
        self, request_id: UUID, requester_id: UUID
    ) -> CustomerReleaseView | None: ...

    async def accept(
        self,
        package_id: UUID,
        recipient_id: UUID,
        idempotency_key: UUID,
        *,
        now: datetime,
    ) -> PackageRecord: ...

    async def access(
        self, artefact_id: UUID, requester_id: UUID
    ) -> ReleaseAccessRecord | None: ...
