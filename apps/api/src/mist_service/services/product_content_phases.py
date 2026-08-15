"""Fenced transactional phases for upload bytes and scanner decisions."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from mist_service.domain import Actor
from mist_service.product_errors import (
    ProductConflict,
    ProductDependencyUnavailable,
    ProductNotFound,
)
from mist_service.product_types import (
    ScanDecision,
    StoredObject,
    UploadIntentRecord,
)
from mist_service.schemas.products import (
    PackageView,
    UploadContentReceipt,
    VersionCommand,
)
from mist_service.services.product_repository_port import (
    ProductUploadServiceRepository,
)
from mist_service.services.product_service_support import ProductServiceSupport
from mist_service.services.product_transfer_types import (
    ContentOperation,
    ScanOperation,
)


class ProductContentPhases(ProductServiceSupport[ProductUploadServiceRepository]):
    """Never call storage or the scanner while a transaction is active."""

    def __init__(
        self,
        repository: ProductUploadServiceRepository,
        *,
        managed_file_uploads_enabled: bool = True,
    ) -> None:
        super().__init__(repository)
        self._managed_file_uploads_enabled = managed_file_uploads_enabled

    async def claim_content(
        self,
        actor: Actor,
        package_id: UUID,
        intent_id: UUID,
        *,
        expected_version: int,
        upload_token: str,
        lease_ttl: timedelta,
    ) -> ContentOperation:
        self._require_managed_file_uploads()
        package, request = await self._authorised_package(actor, package_id, lock=True)
        await self._require_draft_author(actor, package, request)
        row = await self._repository.upload_intent(package_id, intent_id, lock=True)
        if row is None:
            raise ProductNotFound()
        _artefact, intent = row
        token_hash = self._token_hash(upload_token)
        stored_hash = await self._repository.upload_token_hash(intent.id)
        valid_token = stored_hash is not None and hmac.compare_digest(
            token_hash, stored_hash
        )
        if intent.uploaded_at is not None and valid_token:
            return self._content_operation(
                package.id,
                package.version,
                expected_version,
                intent,
                token_hash,
            )
        now = datetime.now(UTC)
        if (
            package.version != expected_version
            or not valid_token
            or intent.consumed_at is not None
            or self._aware(intent.expires_at) <= now
        ):
            raise ProductNotFound()
        owner = uuid4().hex
        generation = await self._repository.claim_intent_operation(
            intent.id,
            owner=owner,
            now=now,
            expires_at=now + lease_ttl,
        )
        return self._content_operation(
            package.id,
            package.version,
            expected_version,
            intent,
            token_hash,
            owner,
            generation,
        )

    async def finalise_content(
        self,
        actor: Actor,
        operation: ContentOperation,
        stored: StoredObject,
    ) -> UploadContentReceipt:
        owner, generation = self._required_lease(operation)
        package, request = await self._authorised_package(
            actor, operation.package_id, lock=True
        )
        await self._require_draft_author(actor, package, request)
        row = await self._repository.upload_intent(
            operation.package_id, operation.intent_id, lock=True
        )
        if row is None:
            raise ProductNotFound()
        _artefact, intent = row
        await self._repository.require_intent_operation(
            intent.id, owner=owner, generation=generation
        )
        stored_hash = await self._repository.upload_token_hash(intent.id)
        now = datetime.now(UTC)
        if (
            package.version != operation.expected_version
            or stored_hash is None
            or not hmac.compare_digest(operation.token_hash, stored_hash)
            or intent.uploaded_at is not None
            or intent.consumed_at is not None
            or self._aware(intent.expires_at) <= now
        ):
            raise ProductConflict()
        await self._repository.mark_uploaded(intent.id, now=now)
        await self._repository.release_intent_operation(
            intent.id, owner=owner, generation=generation
        )
        view = await self._repository.view(package.id)
        return UploadContentReceipt(
            intent_id=intent.id,
            size_bytes=stored.size_bytes,
            sha256=stored.checksum,
            uploaded_at=now,
            package_version=view.version,
        )

    async def claim_scan(
        self,
        actor: Actor,
        package_id: UUID,
        intent_id: UUID,
        command: VersionCommand,
        *,
        lease_ttl: timedelta,
    ) -> ScanOperation | PackageView:
        self._require_managed_file_uploads()
        package, request = await self._authorised_package(actor, package_id, lock=True)
        await self._require_draft_author(actor, package, request)
        row = await self._repository.upload_intent(package_id, intent_id, lock=True)
        if row is None:
            raise ProductNotFound()
        artefact, intent = row
        if intent.consumed_at is not None:
            return await self._repository.view(package_id)
        now = datetime.now(UTC)
        if (
            package.version != command.expected_version
            or intent.uploaded_at is None
            or self._aware(intent.expires_at) <= now
            or artefact.filename is None
            or artefact.media_type is None
        ):
            raise ProductConflict("The upload intent is unavailable.")
        owner = uuid4().hex
        generation = await self._repository.claim_intent_operation(
            intent.id,
            owner=owner,
            now=now,
            expires_at=now + lease_ttl,
        )
        return ScanOperation(
            package.id,
            intent.id,
            artefact.id,
            intent.object_key,
            artefact.filename,
            artefact.media_type,
            intent.expected_size_bytes,
            intent.expected_checksum,
            command.expected_version,
            command.idempotency_key,
            owner,
            generation,
        )

    async def finalise_scan(
        self,
        actor: Actor,
        operation: ScanOperation,
        decision: ScanDecision,
        released_key: str | None,
    ) -> PackageView:
        package, request = await self._authorised_package(
            actor, operation.package_id, lock=True
        )
        await self._require_draft_author(actor, package, request)
        row = await self._repository.upload_intent(
            operation.package_id, operation.intent_id, lock=True
        )
        if row is None:
            raise ProductNotFound()
        artefact, intent = row
        await self._repository.require_intent_operation(
            intent.id,
            owner=operation.owner,
            generation=operation.generation,
        )
        if (
            package.version != operation.expected_version
            or artefact.id != operation.artefact_id
            or intent.uploaded_at is None
            or intent.consumed_at is not None
        ):
            raise ProductConflict()
        await self._repository.record_scan(
            artefact.id,
            operation.idempotency_key,
            decision,
            operation.expected_checksum,
            released_key,
        )
        await self._repository.release_intent_operation(
            intent.id,
            owner=operation.owner,
            generation=operation.generation,
        )
        return await self._repository.view(package.id)

    async def release_operation(
        self,
        intent_id: UUID,
        owner: str | None,
        generation: int | None,
    ) -> None:
        if owner is not None and generation is not None:
            await self._repository.release_intent_operation(
                intent_id, owner=owner, generation=generation
            )

    @staticmethod
    def receipt_for_existing(
        operation: ContentOperation,
        stored: StoredObject,
    ) -> UploadContentReceipt:
        if operation.uploaded_at is None:
            raise ProductConflict()
        return UploadContentReceipt(
            intent_id=operation.intent_id,
            size_bytes=stored.size_bytes,
            sha256=stored.checksum,
            uploaded_at=operation.uploaded_at,
            package_version=operation.package_version,
        )

    @staticmethod
    def _content_operation(
        package_id: UUID,
        package_version: int,
        expected_version: int,
        intent: UploadIntentRecord,
        token_hash: str,
        owner: str | None = None,
        generation: int | None = None,
    ) -> ContentOperation:
        return ContentOperation(
            package_id=package_id,
            intent_id=intent.id,
            object_key=intent.object_key,
            expected_version=expected_version,
            expected_size=intent.expected_size_bytes,
            expected_checksum=intent.expected_checksum,
            token_hash=token_hash,
            owner=owner,
            generation=generation,
            uploaded_at=intent.uploaded_at,
            package_version=package_version,
        )

    @staticmethod
    def _required_lease(operation: ContentOperation) -> tuple[str, int]:
        if operation.owner is None or operation.generation is None:
            raise ProductConflict()
        return operation.owner, operation.generation

    def _require_managed_file_uploads(self) -> None:
        if not self._managed_file_uploads_enabled:
            raise ProductDependencyUnavailable(
                "Managed-file uploads are unavailable in this environment."
            )
