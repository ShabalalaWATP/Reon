"""Application port for managed-product metadata persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from istari_service.domain import Actor
from istari_service.product_types import (
    ArtefactRecord,
    PackageRecord,
    ProductRequestRecord,
    ReleaseAccessRecord,
    ScanDecision,
    UploadIntentRecord,
)
from istari_service.schemas.products import CustomerReleaseView, PackageView


class ProductRepository(Protocol):
    async def active_actor(self, actor: Actor) -> bool: ...

    async def request(
        self, request_id: UUID, *, lock: bool
    ) -> ProductRequestRecord | None: ...

    async def create_package(
        self, request_id: UUID, actor_id: UUID, creation_key: UUID
    ) -> PackageRecord: ...

    async def package(
        self, package_id: UUID, *, lock: bool
    ) -> PackageRecord | None: ...

    async def latest_package(self, request_id: UUID) -> PackageRecord | None: ...

    async def view(self, package_id: UUID) -> PackageView: ...

    async def approved_link_domains(
        self, request_id: UUID
    ) -> frozenset[str] | None: ...

    async def storage_usage(
        self, package_id: UUID, request_id: UUID, author_id: UUID
    ) -> tuple[int, int, int, int, int, int, int, int]: ...

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

    async def upload_intent(
        self, package_id: UUID, intent_id: UUID, *, lock: bool
    ) -> tuple[ArtefactRecord, UploadIntentRecord] | None: ...

    async def upload_token_hash(self, intent_id: UUID) -> str | None: ...

    async def mark_uploaded(self, intent_id: UUID, *, now: datetime) -> None: ...

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

    async def record_scan(
        self,
        artefact_id: UUID,
        idempotency_key: UUID,
        decision: ScanDecision,
        checksum: str,
        released_key: str | None,
    ) -> ArtefactRecord: ...

    async def package_digest(self, package_id: UUID) -> tuple[str, int, int]: ...
    async def freeze(self, package_id: UUID, checksum: str) -> PackageRecord: ...

    async def approve(
        self, package_id: UUID, actor_id: UUID, *, now: datetime
    ) -> PackageRecord: ...

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

    async def accept(
        self,
        package_id: UUID,
        recipient_id: UUID,
        idempotency_key: UUID,
        *,
        now: datetime,
    ) -> PackageRecord: ...

    async def withdraw(
        self,
        package_id: UUID,
        actor_id: UUID,
        reason: str,
        *,
        now: datetime,
    ) -> PackageRecord: ...

    async def release_view(
        self, request_id: UUID, requester_id: UUID
    ) -> CustomerReleaseView | None: ...

    async def access(
        self, artefact_id: UUID, requester_id: UUID
    ) -> ReleaseAccessRecord | None: ...
