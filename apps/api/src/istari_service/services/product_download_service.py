"""Release the database before opening a potentially slow product stream."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.domain import Actor
from istari_service.product_access_audit import SqlAlchemyProductAccessAudit
from istari_service.product_runtime import ProductRuntime
from istari_service.product_types import DownloadStream
from istari_service.repositories.products import SqlAlchemyProductRepository
from istari_service.services.product_service import ProductService


class ProductDownloadService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        runtime: ProductRuntime,
    ) -> None:
        self._sessions = sessions
        self._runtime = runtime

    async def download(
        self,
        actor: Actor,
        artefact_id: UUID,
        correlation_id: str | None,
    ) -> DownloadStream:
        service: ProductService
        async with self._sessions() as session, session.begin():
            service = ProductService(
                SqlAlchemyProductRepository(session),
                self._runtime.storage,
                self._runtime.scanner,
                self._runtime.link_policy,
                SqlAlchemyProductAccessAudit(self._sessions),
                upload_ttl=self._runtime.upload_ttl,
                maximum_file_bytes=self._runtime.maximum_file_bytes,
                maximum_package_bytes=self._runtime.maximum_package_bytes,
                maximum_request_storage_bytes=(
                    self._runtime.maximum_request_storage_bytes
                ),
                maximum_user_storage_bytes=self._runtime.maximum_user_storage_bytes,
                maximum_global_storage_bytes=(
                    self._runtime.maximum_global_storage_bytes
                ),
                managed_file_uploads_enabled=(
                    self._runtime.managed_file_uploads_enabled
                ),
            )
            access = await service.authorise_download(
                actor, artefact_id, correlation_id
            )
        return await service.download_authorised(
            actor,
            access,
            correlation_id,
        )
