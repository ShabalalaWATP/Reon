"""Durable retry support for single-purpose managed-product upload grants."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.product_errors import ProductNotFound
from istari_service.product_models import ProductArtefact, ProductUploadIntent
from istari_service.product_types import ArtefactRecord, UploadIntentRecord
from istari_service.repositories.product_records import artefact_record, intent_record


class ProductUploadRetryRepositoryMixin:
    session: AsyncSession

    async def managed_retry(
        self, package_id: UUID, creation_key: UUID
    ) -> tuple[ArtefactRecord, UploadIntentRecord] | None:
        row = (
            await self.session.execute(
                select(ProductArtefact, ProductUploadIntent)
                .join(
                    ProductUploadIntent,
                    ProductUploadIntent.artefact_id == ProductArtefact.id,
                )
                .where(ProductArtefact.creation_key == creation_key)
                .with_for_update()
            )
        ).one_or_none()
        if row is None:
            return None
        if row[0].package_id != package_id:
            raise ProductNotFound()
        return artefact_record(row[0]), intent_record(row[1])

    async def refresh_upload_grant(
        self,
        intent_id: UUID,
        *,
        token_hash: str,
        expires_at: datetime,
    ) -> UploadIntentRecord:
        intent = await self.session.get(ProductUploadIntent, intent_id)
        if intent is None:
            raise ProductNotFound()
        intent.token_hash = token_hash
        intent.expires_at = expires_at
        await self.session.flush()
        return intent_record(intent)
