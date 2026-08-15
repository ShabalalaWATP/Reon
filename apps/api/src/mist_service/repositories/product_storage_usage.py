"""Bounded storage accounting for managed-product reservations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from mist_service.models import ServiceRequest, User
from mist_service.product_models import (
    ProductArtefact,
    ProductPackage,
    ProductStorageQuota,
    ProductUploadIntent,
)
from mist_service.product_types import (
    ArtefactKind,
    ArtefactLifecycle,
    ProductStorageUsage,
)


class ProductStorageUsageRepositoryMixin:
    session: AsyncSession

    async def storage_usage(
        self, package_id: UUID, request_id: UUID, author_id: UUID
    ) -> ProductStorageUsage:
        await self._lock_storage_scopes(package_id, request_id, author_id)
        counted = ProductArtefact.lifecycle.notin_(
            [ArtefactLifecycle.FAILED, ArtefactLifecycle.EXPIRED]
        )
        size = func.coalesce(func.sum(ProductArtefact.size_bytes), 0)

        async def total(*conditions: ColumnElement[bool]) -> int:
            value = await self.session.scalar(
                select(size)
                .select_from(ProductArtefact)
                .join(ProductPackage, ProductPackage.id == ProductArtefact.package_id)
                .where(
                    ProductArtefact.kind == ArtefactKind.MANAGED_FILE,
                    counted,
                    *conditions,
                )
            )
            return int(value or 0)

        async def active(*conditions: ColumnElement[bool]) -> int:
            value = await self.session.scalar(
                select(func.count())
                .select_from(ProductUploadIntent)
                .join(
                    ProductArtefact,
                    ProductArtefact.id == ProductUploadIntent.artefact_id,
                )
                .join(ProductPackage, ProductPackage.id == ProductArtefact.package_id)
                .where(ProductUploadIntent.consumed_at.is_(None), *conditions)
            )
            return int(value or 0)

        return ProductStorageUsage(
            package_bytes=await total(ProductPackage.id == package_id),
            request_bytes=await total(ProductPackage.request_id == request_id),
            user_bytes=await total(ProductPackage.author_user_id == author_id),
            service_bytes=await total(),
            package_active_intents=await active(ProductPackage.id == package_id),
            request_active_intents=await active(
                ProductPackage.request_id == request_id
            ),
            user_active_intents=await active(
                ProductPackage.author_user_id == author_id
            ),
            service_active_intents=await active(),
        )

    async def _lock_storage_scopes(
        self, package_id: UUID, request_id: UUID, author_id: UUID
    ) -> None:
        quota = await self.session.get(ProductStorageQuota, 1, with_for_update=True)
        if quota is None:
            quota = ProductStorageQuota(id=1)
            self.session.add(quota)
            await self.session.flush()
        for model, identifier in (
            (User, author_id),
            (ServiceRequest, request_id),
            (ProductPackage, package_id),
        ):
            await self.session.scalar(
                select(model.id).where(model.id == identifier).with_for_update()
            )
