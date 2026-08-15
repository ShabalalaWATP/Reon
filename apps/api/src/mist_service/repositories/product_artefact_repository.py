"""Managed-file and external-link artefact persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.product_errors import ProductConflict, ProductNotFound
from mist_service.product_models import (
    ExternalProductLink,
    ProductArtefact,
    ProductPackage,
    ProductScan,
    ProductUploadIntent,
)
from mist_service.product_types import (
    ArtefactKind,
    ArtefactLifecycle,
    ArtefactRecord,
    ScanDecision,
    UploadIntentRecord,
)
from mist_service.repositories.product_records import artefact_record, intent_record


class ProductArtefactRepositoryMixin:
    session: AsyncSession

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
        count = await self._artefact_count(package_id)
        if count >= 10:
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
        await self._bump_package_version(package_id)
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
        count = await self._artefact_count(package_id)
        if count >= 10:
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
        await self._bump_package_version(package_id)
        await self.session.flush()
        return artefact_record(artefact, link)

    async def upload_intent(
        self, package_id: UUID, intent_id: UUID, *, lock: bool
    ) -> tuple[ArtefactRecord, UploadIntentRecord] | None:
        query = (
            select(ProductUploadIntent, ProductArtefact)
            .join(
                ProductArtefact,
                ProductArtefact.id == ProductUploadIntent.artefact_id,
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
        await self._bump_package_version(artefact.package_id)

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
            await self._bump_package_version(artefact.package_id)
            intent = await self.session.scalar(
                select(ProductUploadIntent)
                .where(ProductUploadIntent.artefact_id == artefact_id)
                .order_by(ProductUploadIntent.created_at.desc())
            )
            if intent:
                intent.consumed_at = datetime.now(UTC)
        await self.session.flush()
        return artefact_record(artefact)

    async def _artefact_count(self, package_id: UUID) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(ProductArtefact)
            .where(ProductArtefact.package_id == package_id)
        )
        return int(count or 0)

    async def _bump_package_version(self, package_id: UUID) -> None:
        package = await self.session.get(ProductPackage, package_id)
        if package:
            package.version += 1
