"""Shared transaction, lease and cleanup boundary for product transfers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.product_errors import ProductDependencyUnavailable
from istari_service.product_ports import ProductAccessAudit
from istari_service.product_runtime import ProductRuntime
from istari_service.repositories.products import SqlAlchemyProductRepository
from istari_service.services.product_content_phases import ProductContentPhases
from istari_service.services.product_managed_phases import ProductManagedPhases
from istari_service.services.product_transfer_types import (
    ContentOperation,
    ScanOperation,
)

MINIMUM_OPERATION_LEASE = timedelta(minutes=2)
LOGGER = logging.getLogger(__name__)


class ProductTransferContext:
    """Own shared adapters while focused coordinators own individual use cases."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        runtime: ProductRuntime,
        audit: ProductAccessAudit,
    ) -> None:
        self.sessions = sessions
        self.runtime = runtime
        self.audit = audit
        self.lease_ttl = max(runtime.upload_ttl, MINIMUM_OPERATION_LEASE)

    def managed_phases(self, session: AsyncSession) -> ProductManagedPhases:
        return ProductManagedPhases(
            SqlAlchemyProductRepository(session),
            self.runtime.storage,
            self.runtime.scanner,
            self.runtime.link_policy,
            self.audit,
            upload_ttl=self.runtime.upload_ttl,
            maximum_file_bytes=self.runtime.maximum_file_bytes,
            maximum_package_bytes=self.runtime.maximum_package_bytes,
            maximum_request_storage_bytes=self.runtime.maximum_request_storage_bytes,
            maximum_user_storage_bytes=self.runtime.maximum_user_storage_bytes,
            maximum_global_storage_bytes=self.runtime.maximum_global_storage_bytes,
            managed_file_uploads_enabled=self.runtime.managed_file_uploads_enabled,
        )

    def content_phases(self, session: AsyncSession) -> ProductContentPhases:
        return ProductContentPhases(
            SqlAlchemyProductRepository(session),
            self.runtime.storage,
            self.runtime.scanner,
            self.runtime.link_policy,
            self.audit,
            upload_ttl=self.runtime.upload_ttl,
            maximum_file_bytes=self.runtime.maximum_file_bytes,
            maximum_package_bytes=self.runtime.maximum_package_bytes,
            maximum_request_storage_bytes=self.runtime.maximum_request_storage_bytes,
            maximum_user_storage_bytes=self.runtime.maximum_user_storage_bytes,
            maximum_global_storage_bytes=self.runtime.maximum_global_storage_bytes,
            managed_file_uploads_enabled=self.runtime.managed_file_uploads_enabled,
        )

    async def release_after_failure(
        self, operation: ContentOperation | ScanOperation
    ) -> None:
        try:
            async with self.sessions() as session, session.begin():
                await self.content_phases(session).release_operation(
                    operation.intent_id,
                    operation.owner,
                    operation.generation,
                )
        except Exception:
            LOGGER.exception("Failed to release a managed-product operation lease.")

    async def discard_quarantine(self, object_key: str) -> None:
        try:
            await self.runtime.storage.delete_quarantine(object_key)
        except ProductDependencyUnavailable:
            return

    async def discard_released(self, object_key: str) -> None:
        try:
            await self.runtime.storage.delete_released(object_key)
        except ProductDependencyUnavailable:
            return

    def upload_expires_at(self) -> datetime:
        return datetime.now(UTC) + self.runtime.upload_ttl
