"""Quarantined byte-transfer use case."""

from __future__ import annotations

from collections.abc import AsyncIterable
from uuid import UUID

from istari_service.domain import Actor
from istari_service.product_errors import ProductValidationFailed
from istari_service.schemas.products import UploadContentReceipt
from istari_service.services.product_content_phases import ProductContentPhases
from istari_service.services.product_transfer_context import ProductTransferContext


class ProductContentTransfer:
    def __init__(self, context: ProductTransferContext) -> None:
        self._context = context

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
        async with self._context.sessions() as session, session.begin():
            operation = await self._context.content_phases(session).claim_content(
                actor,
                package_id,
                intent_id,
                expected_version=expected_version,
                upload_token=upload_token,
                lease_ttl=self._context.lease_ttl,
            )
        if operation.uploaded_at is not None:
            stored = await self._context.runtime.storage.read_quarantine(
                operation.object_key
            )
            return ProductContentPhases.receipt_for_existing(operation, stored)
        try:
            stored = await self._context.runtime.storage.write_quarantine(
                operation.object_key,
                chunks,
                maximum_bytes=min(
                    self._context.runtime.maximum_file_bytes,
                    operation.expected_size,
                ),
            )
            if (
                stored.size_bytes != operation.expected_size
                or stored.checksum != operation.expected_checksum
            ):
                await self._context.runtime.storage.delete_quarantine(
                    operation.object_key
                )
                raise ProductValidationFailed(
                    "The uploaded bytes do not match the intent."
                )
            async with self._context.sessions() as session, session.begin():
                return await self._context.content_phases(session).finalise_content(
                    actor, operation, stored
                )
        except Exception:
            await self._context.release_after_failure(operation)
            raise
