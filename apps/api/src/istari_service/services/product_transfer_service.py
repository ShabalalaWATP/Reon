"""Transaction-scoped orchestration of product storage and scanner I/O."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.domain import Actor
from istari_service.product_errors import (
    ProductDependencyUnavailable,
    ProductValidationFailed,
)
from istari_service.product_ports import ProductAccessAudit
from istari_service.product_runtime import ProductRuntime
from istari_service.product_types import ScanResult
from istari_service.repositories.products import SqlAlchemyProductRepository
from istari_service.schemas.products import (
    ManagedArtefactCreate,
    ManagedArtefactIntent,
    PackageView,
    UploadContentReceipt,
    VersionCommand,
)
from istari_service.services.product_content_phases import ProductContentPhases
from istari_service.services.product_managed_phases import ProductManagedPhases
from istari_service.services.product_transfer_types import (
    ContentOperation,
    ScanOperation,
)

MINIMUM_OPERATION_LEASE = timedelta(minutes=2)
LOGGER = logging.getLogger(__name__)


class ProductTransferService:
    """Keep external I/O strictly between committed, fenced database phases."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        runtime: ProductRuntime,
        audit: ProductAccessAudit,
    ) -> None:
        self._sessions = sessions
        self._runtime = runtime
        self._audit = audit
        self._lease_ttl = max(runtime.upload_ttl, MINIMUM_OPERATION_LEASE)

    async def add_managed(
        self,
        actor: Actor,
        package_id: UUID,
        command: ManagedArtefactCreate,
    ) -> ManagedArtefactIntent:
        async with self._sessions() as session, session.begin():
            plan = await self._managed_phases(session).prepare_managed(
                actor, package_id, command
            )
        grant = await self._runtime.storage.issue_upload(
            plan.object_key,
            expires_at=self._now_plus_upload_ttl(),
        )
        async with self._sessions() as session, session.begin():
            return await self._managed_phases(session).finalise_managed(
                actor, plan, grant
            )

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
        async with self._sessions() as session, session.begin():
            operation = await self._content_phases(session).claim_content(
                actor,
                package_id,
                intent_id,
                expected_version=expected_version,
                upload_token=upload_token,
                lease_ttl=self._lease_ttl,
            )
        if operation.uploaded_at is not None:
            stored = await self._runtime.storage.read_quarantine(operation.object_key)
            return ProductContentPhases.receipt_for_existing(operation, stored)
        try:
            stored = await self._runtime.storage.write_quarantine(
                operation.object_key,
                chunks,
                maximum_bytes=min(
                    self._runtime.maximum_file_bytes,
                    operation.expected_size,
                ),
            )
            if (
                stored.size_bytes != operation.expected_size
                or stored.checksum != operation.expected_checksum
            ):
                await self._runtime.storage.delete_quarantine(operation.object_key)
                raise ProductValidationFailed(
                    "The uploaded bytes do not match the intent."
                )
            async with self._sessions() as session, session.begin():
                return await self._content_phases(session).finalise_content(
                    actor, operation, stored
                )
        except Exception:
            await self._release_after_failure(operation)
            raise

    async def complete_upload(
        self,
        actor: Actor,
        package_id: UUID,
        intent_id: UUID,
        command: VersionCommand,
    ) -> PackageView:
        async with self._sessions() as session, session.begin():
            operation = await self._content_phases(session).claim_scan(
                actor,
                package_id,
                intent_id,
                command,
                lease_ttl=self._lease_ttl,
            )
        if isinstance(operation, PackageView):
            return operation
        try:
            decision = await self._runtime.scanner.scan(
                self._runtime.storage.stream_quarantine(operation.object_key),
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
                await self._runtime.storage.promote(operation.object_key, released_key)
            async with self._sessions() as session, session.begin():
                view = await self._content_phases(session).finalise_scan(
                    actor,
                    operation,
                    decision,
                    released_key,
                )
        except Exception:
            await self._release_after_failure(operation)
            raise
        await self._discard_quarantine(operation.object_key)
        return view

    async def _release(self, operation: ContentOperation | ScanOperation) -> None:
        async with self._sessions() as session, session.begin():
            await self._content_phases(session).release_operation(
                operation.intent_id,
                operation.owner,
                operation.generation,
            )

    async def _release_after_failure(
        self, operation: ContentOperation | ScanOperation
    ) -> None:
        try:
            await self._release(operation)
        except Exception:
            LOGGER.exception("Failed to release a managed-product operation lease.")

    async def _discard_quarantine(self, object_key: str) -> None:
        try:
            await self._runtime.storage.delete_quarantine(object_key)
        except ProductDependencyUnavailable:
            return

    def _managed_phases(self, session: AsyncSession) -> ProductManagedPhases:
        return ProductManagedPhases(
            SqlAlchemyProductRepository(session),
            self._runtime.storage,
            self._runtime.scanner,
            self._runtime.link_policy,
            self._audit,
            upload_ttl=self._runtime.upload_ttl,
            maximum_file_bytes=self._runtime.maximum_file_bytes,
            maximum_package_bytes=self._runtime.maximum_package_bytes,
            managed_file_uploads_enabled=(self._runtime.managed_file_uploads_enabled),
        )

    def _content_phases(self, session: AsyncSession) -> ProductContentPhases:
        return ProductContentPhases(
            SqlAlchemyProductRepository(session),
            self._runtime.storage,
            self._runtime.scanner,
            self._runtime.link_policy,
            self._audit,
            upload_ttl=self._runtime.upload_ttl,
            maximum_file_bytes=self._runtime.maximum_file_bytes,
            maximum_package_bytes=self._runtime.maximum_package_bytes,
            managed_file_uploads_enabled=(self._runtime.managed_file_uploads_enabled),
        )

    def _now_plus_upload_ttl(self) -> datetime:
        return datetime.now(UTC) + self._runtime.upload_ttl
