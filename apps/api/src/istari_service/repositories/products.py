"""SQLAlchemy adapter for immutable managed-product metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.product_errors import ProductConflict, ProductNotFound
from istari_service.product_models import (
    ExternalProductLink,
    ProductArtefact,
    ProductPackage,
    ProductScan,
    ProductUploadIntent,
)
from istari_service.product_types import (
    ArtefactKind,
    ArtefactLifecycle,
    ArtefactRecord,
    PackageRecord,
    PackageStatus,
    ScanDecision,
    UploadIntentRecord,
)
from istari_service.repositories.product_configuration import (
    ProductConfigurationRepositoryMixin,
)
from istari_service.repositories.product_lifecycle import ProductLifecycleMixin
from istari_service.repositories.product_operation_leases import (
    ProductOperationLeaseRepositoryMixin,
)
from istari_service.repositories.product_records import (
    artefact_record,
    intent_record,
    package_record,
)
from istari_service.repositories.product_requests import ProductRequestRepositoryMixin
from istari_service.repositories.product_storage_usage import (
    ProductStorageUsageRepositoryMixin,
)
from istari_service.repositories.product_upload_retries import (
    ProductUploadRetryRepositoryMixin,
)
from istari_service.repositories.product_views import package_view
from istari_service.schemas.products import (
    PackageView,
)

MAX_PACKAGE_VERSIONS_PER_REQUEST = 100


class SqlAlchemyProductRepository(
    ProductConfigurationRepositoryMixin,
    ProductOperationLeaseRepositoryMixin,
    ProductUploadRetryRepositoryMixin,
    ProductLifecycleMixin,
    ProductRequestRepositoryMixin,
    ProductStorageUsageRepositoryMixin,
):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_package(
        self, request_id: UUID, actor_id: UUID, creation_key: UUID
    ) -> PackageRecord:
        existing = await self.session.scalar(
            select(ProductPackage).where(ProductPackage.creation_key == creation_key)
        )
        if existing:
            if existing.request_id != request_id or existing.author_user_id != actor_id:
                raise ProductNotFound()
            return package_record(existing)
        latest = await self.session.scalar(
            select(func.max(ProductPackage.package_version)).where(
                ProductPackage.request_id == request_id
            )
        )
        active_drafts = await self.session.scalar(
            select(func.count())
            .select_from(ProductPackage)
            .where(
                ProductPackage.request_id == request_id,
                ProductPackage.status == PackageStatus.DRAFT,
            )
        )
        if active_drafts:
            raise ProductConflict("The request already has an active product draft.")
        if (latest or 0) >= MAX_PACKAGE_VERSIONS_PER_REQUEST:
            raise ProductConflict("The request has reached its product-version limit.")
        package = ProductPackage(
            request_id=request_id,
            package_version=(latest or 0) + 1,
            creation_key=creation_key,
            author_user_id=actor_id,
            status=PackageStatus.DRAFT,
            version=1,
        )
        self.session.add(package)
        await self.session.flush()
        return package_record(package)

    async def package(self, package_id: UUID, *, lock: bool) -> PackageRecord | None:
        query = select(ProductPackage).where(ProductPackage.id == package_id)
        if lock:
            query = query.with_for_update()
        package = await self.session.scalar(query)
        return package_record(package) if package else None

    async def latest_package(self, request_id: UUID) -> PackageRecord | None:
        package = await self.session.scalar(
            select(ProductPackage)
            .where(ProductPackage.request_id == request_id)
            .order_by(ProductPackage.package_version.desc())
            .limit(1)
        )
        return package_record(package) if package else None

    async def view(self, package_id: UUID) -> PackageView:
        package = await self.session.get(ProductPackage, package_id)
        if package is None:
            raise ProductNotFound()
        return await package_view(self.session, package)

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
    ) -> tuple[ArtefactRecord, UploadIntentRecord]:
        existing = await self.session.scalar(
            select(ProductArtefact).where(ProductArtefact.creation_key == creation_key)
        )
        if existing:
            intent = await self.session.scalar(
                select(ProductUploadIntent).where(
                    ProductUploadIntent.artefact_id == existing.id,
                    ProductUploadIntent.idempotency_key == intent_key,
                )
            )
            if existing.package_id != package_id or intent is None:
                raise ProductNotFound()
            return artefact_record(existing), intent_record(intent)
        count = await self.session.scalar(
            select(func.count())
            .select_from(ProductArtefact)
            .where(ProductArtefact.package_id == package_id)
        )
        if count is None or count >= 10:
            raise ProductConflict("A package can contain no more than ten artefacts.")
        artefact = ProductArtefact(
            package_id=package_id,
            position=count + 1,
            creation_key=creation_key,
            kind=ArtefactKind.MANAGED_FILE,
            lifecycle=ArtefactLifecycle.PENDING_UPLOAD,
            label=label,
            filename=filename,
            media_type=media_type,
            size_bytes=size_bytes,
            checksum=checksum,
            quarantine_key=object_key,
            version=1,
        )
        self.session.add(artefact)
        await self.session.flush()
        intent = ProductUploadIntent(
            artefact_id=artefact.id,
            idempotency_key=intent_key,
            object_key=object_key,
            token_hash=token_hash,
            expected_size_bytes=size_bytes,
            expected_media_type=media_type,
            expected_checksum=checksum,
            expires_at=expires_at,
        )
        self.session.add(intent)
        package = await self.session.get(ProductPackage, package_id)
        if package:
            package.version += 1
        await self.session.flush()
        return artefact_record(artefact), intent_record(intent)

    async def create_external(
        self,
        package_id: UUID,
        *,
        label: str,
        destination: str,
        domain: str,
        expires_at: datetime | None,
        creation_key: UUID,
    ) -> ArtefactRecord:
        existing = await self.session.scalar(
            select(ProductArtefact).where(ProductArtefact.creation_key == creation_key)
        )
        if existing:
            link = await self.session.scalar(
                select(ExternalProductLink).where(
                    ExternalProductLink.artefact_id == existing.id
                )
            )
            if existing.package_id != package_id or link is None:
                raise ProductNotFound()
            return artefact_record(existing, link)
        count = await self.session.scalar(
            select(func.count())
            .select_from(ProductArtefact)
            .where(ProductArtefact.package_id == package_id)
        )
        if count is None or count >= 10:
            raise ProductConflict("A package can contain no more than ten artefacts.")
        artefact = ProductArtefact(
            package_id=package_id,
            position=count + 1,
            creation_key=creation_key,
            kind=ArtefactKind.EXTERNAL_LINK,
            lifecycle=ArtefactLifecycle.CLEAN,
            label=label,
            version=1,
        )
        self.session.add(artefact)
        await self.session.flush()
        link = ExternalProductLink(
            artefact_id=artefact.id,
            destination_url=destination,
            normalised_domain=domain,
            expires_at=expires_at,
        )
        self.session.add(link)
        package = await self.session.get(ProductPackage, package_id)
        if package:
            package.version += 1
        await self.session.flush()
        return artefact_record(artefact, link)

    async def upload_intent(
        self, package_id: UUID, intent_id: UUID, *, lock: bool
    ) -> tuple[ArtefactRecord, UploadIntentRecord] | None:
        query = (
            select(ProductUploadIntent, ProductArtefact)
            .join(
                ProductArtefact, ProductArtefact.id == ProductUploadIntent.artefact_id
            )
            .where(
                ProductUploadIntent.id == intent_id,
                ProductArtefact.package_id == package_id,
            )
        )
        if lock:
            query = query.with_for_update()
        row = (await self.session.execute(query)).one_or_none()
        return (artefact_record(row[1]), intent_record(row[0])) if row else None

    async def mark_uploaded(self, intent_id: UUID, *, now: datetime) -> None:
        intent = await self.session.get(ProductUploadIntent, intent_id)
        artefact = (
            await self.session.get(ProductArtefact, intent.artefact_id)
            if intent
            else None
        )
        if intent is None or artefact is None:
            raise ProductNotFound()
        intent.uploaded_at = now
        artefact.lifecycle = ArtefactLifecycle.QUARANTINED
        artefact.version += 1
        package = await self.session.get(ProductPackage, artefact.package_id)
        if package:
            package.version += 1

    async def upload_token_hash(self, intent_id: UUID) -> str | None:
        token_hash: str | None = await self.session.scalar(
            select(ProductUploadIntent.token_hash).where(
                ProductUploadIntent.id == intent_id
            )
        )
        return token_hash

    async def record_scan(
        self,
        artefact_id: UUID,
        idempotency_key: UUID,
        decision: ScanDecision,
        checksum: str,
        released_key: str | None,
    ) -> ArtefactRecord:
        existing = await self.session.scalar(
            select(ProductScan).where(
                ProductScan.artefact_id == artefact_id,
                ProductScan.idempotency_key == idempotency_key,
            )
        )
        artefact = await self.session.get(ProductArtefact, artefact_id)
        if artefact is None:
            raise ProductNotFound()
        if existing is None:
            self.session.add(
                ProductScan(
                    artefact_id=artefact_id,
                    idempotency_key=idempotency_key,
                    result=decision.result,
                    scanner=decision.scanner,
                    scanner_version=decision.scanner_version,
                    checksum=checksum,
                    reason_code=decision.reason_code,
                    findings=[],
                )
            )
            artefact.lifecycle = (
                ArtefactLifecycle.CLEAN
                if decision.result.value == "CLEAN"
                else ArtefactLifecycle.FAILED
            )
            artefact.released_key = released_key
            artefact.version += 1
            package = await self.session.get(ProductPackage, artefact.package_id)
            if package:
                package.version += 1
            intent = await self.session.scalar(
                select(ProductUploadIntent)
                .where(ProductUploadIntent.artefact_id == artefact_id)
                .order_by(ProductUploadIntent.created_at.desc())
            )
            if intent:
                intent.consumed_at = datetime.now(UTC)
        await self.session.flush()
        return artefact_record(artefact)
