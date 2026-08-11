"""Scanner decision and clean-object promotion use case."""

from __future__ import annotations

from uuid import UUID

from istari_service.domain import Actor
from istari_service.product_types import ScanResult
from istari_service.schemas.products import PackageView, VersionCommand
from istari_service.services.product_transfer_context import ProductTransferContext


class ProductScanTransfer:
    def __init__(self, context: ProductTransferContext) -> None:
        self._context = context

    async def complete_upload(
        self,
        actor: Actor,
        package_id: UUID,
        intent_id: UUID,
        command: VersionCommand,
    ) -> PackageView:
        async with self._context.sessions() as session, session.begin():
            operation = await self._context.content_phases(session).claim_scan(
                actor,
                package_id,
                intent_id,
                command,
                lease_ttl=self._context.lease_ttl,
            )
        if isinstance(operation, PackageView):
            return operation
        try:
            decision = await self._context.runtime.scanner.scan(
                self._context.runtime.storage.stream_quarantine(operation.object_key),
                filename=operation.filename,
                declared_media_type=operation.media_type,
                expected_size=operation.expected_size,
                expected_checksum=operation.expected_checksum,
            )
            released_key = None
            if decision.result is ScanResult.CLEAN:
                released_key = (
                    f"released/{operation.package_id}/{operation.artefact_id}"
                )
                await self._context.runtime.storage.promote(
                    operation.object_key, released_key
                )
            async with self._context.sessions() as session, session.begin():
                view = await self._context.content_phases(session).finalise_scan(
                    actor,
                    operation,
                    decision,
                    released_key,
                )
        except Exception:
            await self._context.release_after_failure(operation)
            raise
        await self._context.discard_quarantine(operation.object_key)
        return view
