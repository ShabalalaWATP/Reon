"""Bounded managed-file upload, scan and external-link operations."""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from mist_service.domain import Actor
from mist_service.product_errors import (
    ProductConflict,
    ProductNotFound,
    ProductValidationFailed,
)
from mist_service.product_package_policy import (
    require_supported_policy,
    validate_managed_type,
)
from mist_service.product_ports import (
    DocumentScanner,
    ExternalLinkPolicy,
    PrivateObjectStorage,
)
from mist_service.product_quota_policy import (
    MAX_GLOBAL_STORAGE_BYTES,
    MAX_REQUEST_STORAGE_BYTES,
    MAX_USER_STORAGE_BYTES,
)
from mist_service.product_security import (
    MAX_FILE_BYTES,
    MAX_PACKAGE_BYTES,
    validate_managed_metadata,
)
from mist_service.product_types import ArtefactRecord, ScanResult, UploadIntentRecord
from mist_service.schemas.products import (
    ExternalLinkCreate,
    ManagedArtefactCreate,
    ManagedArtefactIntent,
    PackageView,
    UploadContentReceipt,
    UploadIntentView,
    VersionCommand,
)
from mist_service.services.product_repository_port import (
    ProductLinkRepository,
    ProductManagedUploadRepository,
    ProductUploadContentRepository,
    ProductUploadServiceRepository,
)
from mist_service.services.product_service_collaborators import (
    ProductLinkAuthoriser,
    ProductStorageLimits,
    ProductUploadPolicy,
)
from mist_service.services.product_service_support import ProductServiceSupport


class ProductUploadService(ProductServiceSupport[ProductUploadServiceRepository]):
    """Create artefacts and perform the legacy in-transaction upload flow."""

    def __init__(
        self,
        repository: ProductUploadServiceRepository,
        managed_uploads: ProductManagedUploadRepository,
        upload_content: ProductUploadContentRepository,
        links: ProductLinkRepository,
        storage: PrivateObjectStorage,
        scanner: DocumentScanner,
        link_policy: ExternalLinkPolicy,
        *,
        upload_ttl: timedelta = timedelta(minutes=10),
        maximum_file_bytes: int = MAX_FILE_BYTES,
        maximum_package_bytes: int = MAX_PACKAGE_BYTES,
        maximum_request_storage_bytes: int = MAX_REQUEST_STORAGE_BYTES,
        maximum_user_storage_bytes: int = MAX_USER_STORAGE_BYTES,
        maximum_global_storage_bytes: int = MAX_GLOBAL_STORAGE_BYTES,
        managed_file_uploads_enabled: bool = True,
    ) -> None:
        super().__init__(repository)
        self._managed_uploads = managed_uploads
        self._upload_content = upload_content
        self._storage = storage
        self._scanner = scanner
        self._links = ProductLinkAuthoriser(links, link_policy)
        self._upload_policy = ProductUploadPolicy(
            managed_uploads,
            ProductStorageLimits(
                package_bytes=maximum_package_bytes,
                request_bytes=maximum_request_storage_bytes,
                user_bytes=maximum_user_storage_bytes,
                service_bytes=maximum_global_storage_bytes,
            ),
            enabled=managed_file_uploads_enabled,
        )
        self._upload_ttl = upload_ttl
        self._maximum_file_bytes = maximum_file_bytes

    async def add_managed(
        self, actor: Actor, package_id: UUID, command: ManagedArtefactCreate
    ) -> ManagedArtefactIntent:
        self._upload_policy.require_enabled()
        package, request = await self._authorised_package(actor, package_id, lock=True)
        await self._require_draft_author(actor, package, request)
        filename, media_type = validate_managed_metadata(
            filename=command.filename,
            media_type=command.media_type,
            size_bytes=command.size_bytes,
            checksum=command.sha256,
        )
        validate_managed_type(package.policy_version, media_type)
        if command.size_bytes > self._maximum_file_bytes:
            raise ProductValidationFailed(
                "The attachment exceeds the configured limit."
            )
        retry = await self._managed_uploads.managed_retry(
            package.id, command.idempotency_key
        )
        if retry is not None:
            artefact, intent = retry
            if (
                artefact.filename != filename
                or artefact.media_type != media_type
                or artefact.size_bytes != command.size_bytes
                or artefact.checksum != command.sha256.lower()
            ):
                raise ProductConflict(
                    "The idempotency key belongs to different upload metadata."
                )
            expires_at = datetime.now(UTC) + self._upload_ttl
            grant = await self._storage.issue_upload(
                intent.object_key, expires_at=expires_at
            )
            intent = await self._managed_uploads.refresh_upload_grant(
                intent.id,
                token_hash=self._token_hash(grant.token),
                expires_at=grant.expires_at,
            )
            return await self._managed_intent(package.id, artefact, intent, grant.token)
        if package.version != command.expected_version:
            raise ProductConflict()
        await self._upload_policy.require_capacity(package, command.size_bytes)
        object_id = uuid5(package.id, str(command.idempotency_key))
        object_key = f"quarantine/{package.id}/{object_id}"
        expires_at = datetime.now(UTC) + self._upload_ttl
        grant = await self._storage.issue_upload(object_key, expires_at=expires_at)
        artefact, intent = await self._managed_uploads.create_managed(
            package.id,
            label=command.label,
            filename=filename,
            media_type=media_type,
            size_bytes=command.size_bytes,
            checksum=command.sha256.lower(),
            creation_key=command.idempotency_key,
            intent_key=command.idempotency_key,
            object_key=object_key,
            token_hash=self._token_hash(grant.token),
            expires_at=grant.expires_at,
        )
        return await self._managed_intent(package.id, artefact, intent, grant.token)

    async def _managed_intent(
        self,
        package_id: UUID,
        artefact: ArtefactRecord,
        intent: UploadIntentRecord,
        upload_token: str,
    ) -> ManagedArtefactIntent:
        view = await self._repository.view(package_id)
        artefact_view = next(item for item in view.artefacts if item.id == artefact.id)
        return ManagedArtefactIntent(
            package=view,
            artefact=artefact_view,
            upload_intent=UploadIntentView(
                id=intent.id,
                object_key=intent.object_key,
                upload_token=upload_token,
                expires_at=intent.expires_at,
            ),
        )

    async def add_external(
        self, actor: Actor, package_id: UUID, command: ExternalLinkCreate
    ) -> PackageView:
        package, request = await self._editable(
            actor, package_id, command.expected_version
        )
        require_supported_policy(package.policy_version)
        now = datetime.now(UTC)
        if command.expires_at is not None and self._aware(command.expires_at) <= now:
            raise ProductValidationFailed("The external product link has expired.")
        destination, domain = await self._links.approved(request.id, command.url)
        await self._repository.create_external(
            package.id,
            label=command.label,
            destination=destination,
            domain=domain,
            expires_at=command.expires_at,
            creation_key=command.idempotency_key,
        )
        return await self._repository.view(package.id, include_review_details=True)

    async def upload_content(
        self,
        actor: Actor,
        package_id: UUID,
        intent_id: UUID,
        *,
        expected_version: int,
        upload_token: str,
        chunks: AsyncIterable[bytes],
    ) -> UploadContentReceipt:
        self._upload_policy.require_enabled()
        package, request = await self._authorised_package(actor, package_id, lock=True)
        await self._require_draft_author(actor, package, request)
        require_supported_policy(package.policy_version)
        row = await self._upload_content.upload_intent(package_id, intent_id, lock=True)
        if row is None:
            raise ProductNotFound()
        _artefact, intent = row
        now = datetime.now(UTC)
        token_hash = await self._upload_content.upload_token_hash(intent.id)
        valid_token = token_hash is not None and hmac.compare_digest(
            self._token_hash(upload_token), token_hash
        )
        if intent.uploaded_at is not None and valid_token:
            stored = await self._storage.read_quarantine(intent.object_key)
            return UploadContentReceipt(
                intent_id=intent.id,
                size_bytes=stored.size_bytes,
                sha256=stored.checksum,
                uploaded_at=intent.uploaded_at,
                package_version=package.version,
            )
        if (
            package.version != expected_version
            or not valid_token
            or intent.consumed_at is not None
            or self._aware(intent.expires_at) <= now
        ):
            raise ProductNotFound()
        stored = await self._storage.write_quarantine(
            intent.object_key,
            chunks,
            maximum_bytes=min(self._maximum_file_bytes, intent.expected_size_bytes),
        )
        if (
            stored.size_bytes != intent.expected_size_bytes
            or stored.checksum != intent.expected_checksum
        ):
            await self._storage.delete_quarantine(intent.object_key)
            raise ProductValidationFailed("The uploaded bytes do not match the intent.")
        await self._upload_content.mark_uploaded(intent.id, now=now)
        view = await self._repository.view(package.id)
        return UploadContentReceipt(
            intent_id=intent.id,
            size_bytes=stored.size_bytes,
            sha256=stored.checksum,
            uploaded_at=now,
            package_version=view.version,
        )

    async def complete_upload(
        self,
        actor: Actor,
        package_id: UUID,
        intent_id: UUID,
        command: VersionCommand,
    ) -> PackageView:
        self._upload_policy.require_enabled()
        package, request = await self._authorised_package(actor, package_id, lock=True)
        await self._require_draft_author(actor, package, request)
        require_supported_policy(package.policy_version)
        row = await self._upload_content.upload_intent(package_id, intent_id, lock=True)
        if row is None:
            raise ProductNotFound()
        artefact, intent = row
        if intent.consumed_at is not None:
            return await self._repository.view(package_id)
        if package.version != command.expected_version:
            raise ProductConflict()
        if intent.uploaded_at is None or self._aware(intent.expires_at) <= datetime.now(
            UTC
        ):
            raise ProductConflict("The upload intent is unavailable.")
        if artefact.filename is None or artefact.media_type is None:
            raise ProductConflict()
        decision = await self._scanner.scan(
            self._storage.stream_quarantine(intent.object_key),
            filename=artefact.filename,
            declared_media_type=artefact.media_type,
            expected_size=intent.expected_size_bytes,
            expected_checksum=intent.expected_checksum,
        )
        released_key = None
        if decision.result is ScanResult.CLEAN:
            released_key = f"released/{package_id}/{artefact.id}"
            await self._storage.promote(intent.object_key, released_key)
        await self._upload_content.record_scan(
            artefact.id,
            command.idempotency_key,
            decision,
            intent.expected_checksum,
            released_key,
        )
        return await self._repository.view(package_id)


# Temporary import compatibility while callers migrate to the focused name.
ProductUploadOperations = ProductUploadService
