"""Fenced leases for managed-product storage and scanner operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.product_errors import ProductConflict, ProductNotFound
from istari_service.product_models import ProductUploadIntent


class ProductOperationLeaseRepositoryMixin:
    session: AsyncSession

    async def claim_intent_operation(
        self,
        intent_id: UUID,
        *,
        owner: str,
        now: datetime,
        expires_at: datetime,
    ) -> int:
        intent = await self.session.scalar(
            select(ProductUploadIntent)
            .where(ProductUploadIntent.id == intent_id)
            .with_for_update()
        )
        if intent is None:
            raise ProductNotFound()
        lease_expires_at = intent.operation_lease_expires_at
        if lease_expires_at is not None and lease_expires_at.tzinfo is None:
            lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
        if (
            intent.operation_lease_owner is not None
            and lease_expires_at is not None
            and lease_expires_at > now
        ):
            raise ProductConflict("The upload is already being processed.")
        intent.operation_lease_owner = owner
        intent.operation_lease_generation += 1
        intent.operation_lease_expires_at = expires_at
        await self.session.flush()
        return intent.operation_lease_generation

    async def require_intent_operation(
        self,
        intent_id: UUID,
        *,
        owner: str,
        generation: int,
    ) -> None:
        intent = await self.session.scalar(
            select(ProductUploadIntent)
            .where(ProductUploadIntent.id == intent_id)
            .with_for_update()
        )
        if (
            intent is None
            or intent.operation_lease_owner != owner
            or intent.operation_lease_generation != generation
        ):
            raise ProductConflict("The upload operation lease is no longer current.")

    async def release_intent_operation(
        self,
        intent_id: UUID,
        *,
        owner: str,
        generation: int,
    ) -> bool:
        intent = await self.session.scalar(
            select(ProductUploadIntent)
            .where(ProductUploadIntent.id == intent_id)
            .with_for_update()
        )
        if (
            intent is None
            or intent.operation_lease_owner != owner
            or intent.operation_lease_generation != generation
        ):
            return False
        intent.operation_lease_owner = None
        intent.operation_lease_expires_at = None
        await self.session.flush()
        return True
