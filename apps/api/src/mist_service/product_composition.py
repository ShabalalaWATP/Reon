"""Composition boundary for managed-product persistence and coordinators."""

from __future__ import annotations

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.domain import SessionRecord
from mist_service.product_access_audit import SqlAlchemyProductAccessAudit
from mist_service.product_runtime import ProductRuntime
from mist_service.repositories.auth import SqlAlchemyAuthRepository
from mist_service.repositories.products import SqlAlchemyProductRepository
from mist_service.services.product_download_service import ProductDownloadService
from mist_service.services.product_service import (
    ProductService,
    ProductServiceRepositories,
)
from mist_service.services.product_transfer_context import (
    ProductTransferContext,
    ProductTransferRepositories,
)
from mist_service.services.product_transfer_service import ProductTransferService


def build_product_service(
    session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    runtime: ProductRuntime,
) -> ProductService:
    repository = SqlAlchemyProductRepository(session)
    return ProductService(
        ProductServiceRepositories(
            packages=repository,
            review_tasks=repository,
            reviews=repository,
            uploads=repository,
            managed_uploads=repository,
            upload_content=repository,
            links=repository,
            releases=repository,
            customer_releases=repository,
        ),
        runtime.storage,
        runtime.scanner,
        runtime.link_policy,
        SqlAlchemyProductAccessAudit(sessions),
        upload_ttl=runtime.upload_ttl,
        maximum_file_bytes=runtime.maximum_file_bytes,
        maximum_package_bytes=runtime.maximum_package_bytes,
        maximum_request_storage_bytes=runtime.maximum_request_storage_bytes,
        maximum_user_storage_bytes=runtime.maximum_user_storage_bytes,
        maximum_global_storage_bytes=runtime.maximum_global_storage_bytes,
        managed_file_uploads_enabled=runtime.managed_file_uploads_enabled,
    )


def build_transfer_service(
    sessions: async_sessionmaker[AsyncSession],
    runtime: ProductRuntime,
    mutation_session: SessionRecord,
) -> ProductTransferService:
    async def fence(session: object, record: SessionRecord) -> bool:
        database_session = cast(AsyncSession, session)
        return await SqlAlchemyAuthRepository(database_session).lock_mutation_context(
            record.id,
            expected_context_version=record.context_version,
        )

    def repository(session: object) -> SqlAlchemyProductRepository:
        return SqlAlchemyProductRepository(cast(AsyncSession, session))

    return ProductTransferService(
        ProductTransferContext(
            sessions,
            runtime,
            mutation_session,
            ProductTransferRepositories(
                transfers=repository,
                managed_uploads=repository,
                upload_content=repository,
                operation_leases=repository,
            ),
            fence,
        )
    )


def build_download_service(
    sessions: async_sessionmaker[AsyncSession],
    runtime: ProductRuntime,
) -> ProductDownloadService:
    return ProductDownloadService(
        sessions,
        lambda session: build_product_service(session, sessions, runtime),
    )
