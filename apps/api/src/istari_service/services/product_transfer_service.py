"""Compatibility facade over focused managed-product transfer use cases."""

from __future__ import annotations

from collections.abc import AsyncIterable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.domain import Actor
from istari_service.product_ports import ProductAccessAudit
from istari_service.product_runtime import ProductRuntime
from istari_service.schemas.products import (
    ManagedArtefactCreate,
    ManagedArtefactIntent,
    PackageView,
    UploadContentReceipt,
    VersionCommand,
)
from istari_service.services.product_content_transfer import ProductContentTransfer
from istari_service.services.product_managed_transfer import ProductManagedTransfer
from istari_service.services.product_scan_transfer import ProductScanTransfer
from istari_service.services.product_transfer_context import ProductTransferContext


class ProductTransferService:
    """Retain one route contract while each external-I/O path changes alone."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        runtime: ProductRuntime,
        audit: ProductAccessAudit,
    ) -> None:
        context = ProductTransferContext(sessions, runtime, audit)
        self._managed = ProductManagedTransfer(context)
        self._content = ProductContentTransfer(context)
        self._scan = ProductScanTransfer(context)

    async def add_managed(
        self,
        actor: Actor,
        package_id: UUID,
        command: ManagedArtefactCreate,
    ) -> ManagedArtefactIntent:
        return await self._managed.add_managed(actor, package_id, command)

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
        return await self._content.upload_content(
            actor,
            package_id,
            intent_id,
            expected_version=expected_version,
            upload_token=upload_token,
            chunks=chunks,
        )

    async def complete_upload(
        self,
        actor: Actor,
        package_id: UUID,
        intent_id: UUID,
        command: VersionCommand,
    ) -> PackageView:
        return await self._scan.complete_upload(actor, package_id, intent_id, command)
