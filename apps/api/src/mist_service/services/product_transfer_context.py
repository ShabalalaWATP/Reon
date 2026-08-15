"""Shared transaction, lease and cleanup boundary for product transfers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from mist_service.domain import SessionRecord
from mist_service.errors import SessionRequired
from mist_service.product_errors import ProductDependencyUnavailable
from mist_service.product_runtime import ProductRuntime
from mist_service.services.product_content_phases import ProductContentPhases
from mist_service.services.product_managed_phases import ProductManagedPhases
from mist_service.services.product_repository_port import (
    ProductUploadServiceRepository,
)
from mist_service.services.product_transfer_types import (
    ContentOperation,
    ScanOperation,
)

MINIMUM_OPERATION_LEASE = timedelta(minutes=2)
LOGGER = logging.getLogger(__name__)
SessionFactory = Callable[[], Any]
RepositoryFactory = Callable[[Any], ProductUploadServiceRepository]
MutationFence = Callable[[Any, SessionRecord], Awaitable[bool]]


class ProductTransferContext:
    """Own shared adapters while focused coordinators own individual use cases."""

    def __init__(
        self,
        sessions: SessionFactory,
        runtime: ProductRuntime,
        mutation_session: SessionRecord,
        repository_factory: RepositoryFactory,
        mutation_fence: MutationFence,
    ) -> None:
        self.sessions = sessions
        self.runtime = runtime
        self.mutation_session = mutation_session
        self._repository_factory = repository_factory
        self._mutation_fence = mutation_fence
        self.lease_ttl = max(runtime.upload_ttl, MINIMUM_OPERATION_LEASE)

    async def fence(self, session: Any) -> None:
        locked = await self._mutation_fence(session, self.mutation_session)
        if not locked:
            raise SessionRequired()

    def managed_phases(self, session: Any) -> ProductManagedPhases:
        return ProductManagedPhases(
            self._repository_factory(session),
            upload_ttl=self.runtime.upload_ttl,
            maximum_file_bytes=self.runtime.maximum_file_bytes,
            maximum_package_bytes=self.runtime.maximum_package_bytes,
            maximum_request_storage_bytes=self.runtime.maximum_request_storage_bytes,
            maximum_user_storage_bytes=self.runtime.maximum_user_storage_bytes,
            maximum_global_storage_bytes=self.runtime.maximum_global_storage_bytes,
            managed_file_uploads_enabled=self.runtime.managed_file_uploads_enabled,
        )

    def content_phases(self, session: Any) -> ProductContentPhases:
        return ProductContentPhases(
            self._repository_factory(session),
            managed_file_uploads_enabled=self.runtime.managed_file_uploads_enabled,
        )

    async def release_after_failure(
        self, operation: ContentOperation | ScanOperation
    ) -> None:
        try:
            async with self.sessions() as session, session.begin():
                await self.fence(session)
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
