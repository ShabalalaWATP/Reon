"""SQLAlchemy adapter for immutable managed-product metadata."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.product_errors import ProductConflict, ProductNotFound
from istari_service.product_models import ProductPackage
from istari_service.product_package_policy import CURRENT_PACKAGE_POLICY_VERSION
from istari_service.product_types import PackageRecord, PackageStatus
from istari_service.repositories.product_artefact_repository import (
    ProductArtefactRepositoryMixin,
)
from istari_service.repositories.product_configuration import (
    ProductConfigurationRepositoryMixin,
)
from istari_service.repositories.product_lifecycle import ProductLifecycleMixin
from istari_service.repositories.product_operation_leases import (
    ProductOperationLeaseRepositoryMixin,
)
from istari_service.repositories.product_records import package_record
from istari_service.repositories.product_requests import ProductRequestRepositoryMixin
from istari_service.repositories.product_storage_usage import (
    ProductStorageUsageRepositoryMixin,
)
from istari_service.repositories.product_upload_retries import (
    ProductUploadRetryRepositoryMixin,
)
from istari_service.repositories.product_views import package_view
from istari_service.schemas.products import PackageView

MAX_PACKAGE_VERSIONS_PER_REQUEST = 100


class SqlAlchemyProductRepository(
    ProductConfigurationRepositoryMixin,
    ProductOperationLeaseRepositoryMixin,
    ProductUploadRetryRepositoryMixin,
    ProductArtefactRepositoryMixin,
    ProductLifecycleMixin,
    ProductRequestRepositoryMixin,
    ProductStorageUsageRepositoryMixin,
):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_package(
        self, request_id: UUID, actor_id: UUID, creation_key: UUID
    ) -> PackageRecord:
        existing = await self.session.scalar(
            select(ProductPackage).where(ProductPackage.creation_key == creation_key)
        )
        if existing:
            if existing.request_id != request_id or existing.author_user_id != actor_id:
                raise ProductNotFound()
            return package_record(existing)
        latest = await self.session.scalar(
            select(func.max(ProductPackage.package_version)).where(
                ProductPackage.request_id == request_id
            )
        )
        active_drafts = await self.session.scalar(
            select(func.count())
            .select_from(ProductPackage)
            .where(
                ProductPackage.request_id == request_id,
                ProductPackage.status == PackageStatus.DRAFT,
            )
        )
        if active_drafts:
            raise ProductConflict("The request already has an active product draft.")
        if (latest or 0) >= MAX_PACKAGE_VERSIONS_PER_REQUEST:
            raise ProductConflict("The request has reached its product-version limit.")
        await self.require_managed_product_request(request_id)
        package = ProductPackage(
            request_id=request_id,
            package_version=(latest or 0) + 1,
            creation_key=creation_key,
            author_user_id=actor_id,
            status=PackageStatus.DRAFT,
            policy_version=CURRENT_PACKAGE_POLICY_VERSION,
            version=1,
        )
        self.session.add(package)
        await self.session.flush()
        await self.record_managed_package_started(
            request_id,
            actor_id,
            package.id,
            package.package_version,
        )
        return package_record(package)

    async def package(self, package_id: UUID, *, lock: bool) -> PackageRecord | None:
        query = select(ProductPackage).where(ProductPackage.id == package_id)
        if lock:
            query = query.with_for_update()
        package = await self.session.scalar(query)
        return package_record(package) if package else None

    async def latest_package(self, request_id: UUID) -> PackageRecord | None:
        package = await self.session.scalar(
            select(ProductPackage)
            .where(ProductPackage.request_id == request_id)
            .order_by(ProductPackage.package_version.desc())
            .limit(1)
        )
        return package_record(package) if package else None

    async def view(
        self, package_id: UUID, *, include_review_details: bool = False
    ) -> PackageView:
        package = await self.session.get(ProductPackage, package_id)
        if package is None:
            raise ProductNotFound()
        return await package_view(
            self.session,
            package,
            include_review_details=include_review_details,
        )
