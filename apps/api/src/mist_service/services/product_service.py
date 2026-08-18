"""Compatibility facade for focused managed-product application services."""

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from mist_service.domain import Actor
from mist_service.product_ports import (
    DocumentScanner,
    ExternalLinkPolicy,
    PrivateObjectStorage,
    ProductAccessAudit,
)
from mist_service.product_quota_policy import (
    MAX_GLOBAL_STORAGE_BYTES,
    MAX_REQUEST_STORAGE_BYTES,
    MAX_USER_STORAGE_BYTES,
)
from mist_service.product_security import MAX_FILE_BYTES, MAX_PACKAGE_BYTES
from mist_service.product_types import DownloadStream, ReleaseAccessRecord
from mist_service.schemas.products import (
    AcceptanceCommand,
    ApprovalCommand,
    CustomerReleaseView,
    DisseminationCommand,
    ExternalLinkCreate,
    ManagedArtefactCreate,
    ManagedArtefactIntent,
    PackageCreate,
    PackageView,
    SubmitPackageCommand,
    UploadContentReceipt,
    VersionCommand,
    WithdrawalCommand,
)
from mist_service.services.product_customer_release_service import (
    ProductCustomerReleaseService,
)
from mist_service.services.product_package_service import ProductPackageService
from mist_service.services.product_release_service import ProductReleaseService
from mist_service.services.product_repository_port import (
    ProductCustomerReleaseRepository,
    ProductLinkRepository,
    ProductManagedUploadRepository,
    ProductPackageServiceRepository,
    ProductReleaseServiceRepository,
    ProductReviewServiceRepository,
    ProductReviewTaskRepository,
    ProductUploadContentRepository,
    ProductUploadServiceRepository,
)
from mist_service.services.product_review_service import ProductReviewService
from mist_service.services.product_upload_service import ProductUploadService


@dataclass(frozen=True, slots=True)
class ProductServiceRepositories:
    """Explicit narrow persistence roles used by the product facade."""

    packages: ProductPackageServiceRepository
    review_tasks: ProductReviewTaskRepository
    reviews: ProductReviewServiceRepository
    uploads: ProductUploadServiceRepository
    managed_uploads: ProductManagedUploadRepository
    upload_content: ProductUploadContentRepository
    links: ProductLinkRepository
    releases: ProductReleaseServiceRepository
    customer_releases: ProductCustomerReleaseRepository


class ProductService:
    """Preserve the public use-case API while focused services replace it."""

    def __init__(
        self,
        repositories: ProductServiceRepositories,
        storage: PrivateObjectStorage,
        scanner: DocumentScanner,
        link_policy: ExternalLinkPolicy,
        access_audit: ProductAccessAudit,
        *,
        upload_ttl: timedelta = timedelta(minutes=10),
        maximum_file_bytes: int = MAX_FILE_BYTES,
        maximum_package_bytes: int = MAX_PACKAGE_BYTES,
        maximum_request_storage_bytes: int = MAX_REQUEST_STORAGE_BYTES,
        maximum_user_storage_bytes: int = MAX_USER_STORAGE_BYTES,
        maximum_global_storage_bytes: int = MAX_GLOBAL_STORAGE_BYTES,
        managed_file_uploads_enabled: bool = True,
    ) -> None:
        self.packages = ProductPackageService(
            repositories.packages,
            repositories.review_tasks,
            maximum_package_bytes=maximum_package_bytes,
        )
        self.reviews = ProductReviewService(repositories.reviews, storage, access_audit)
        self.uploads = ProductUploadService(
            repositories.uploads,
            repositories.managed_uploads,
            repositories.upload_content,
            repositories.links,
            storage,
            scanner,
            link_policy,
            upload_ttl=upload_ttl,
            maximum_file_bytes=maximum_file_bytes,
            maximum_package_bytes=maximum_package_bytes,
            maximum_request_storage_bytes=maximum_request_storage_bytes,
            maximum_user_storage_bytes=maximum_user_storage_bytes,
            maximum_global_storage_bytes=maximum_global_storage_bytes,
            managed_file_uploads_enabled=managed_file_uploads_enabled,
        )
        self.releases = ProductReleaseService(
            repositories.releases, repositories.review_tasks
        )
        self.customer_access = ProductCustomerReleaseService(
            repositories.customer_releases,
            repositories.links,
            storage,
            link_policy,
            access_audit,
        )

    async def create_package(self, actor: Actor, command: PackageCreate) -> PackageView:
        return await self.packages.create_package(actor, command)

    async def get_package(self, actor: Actor, package_id: UUID) -> PackageView:
        return await self.packages.get_package(actor, package_id)

    async def get_package_for_request(
        self, actor: Actor, request_id: UUID
    ) -> PackageView | None:
        return await self.packages.get_package_for_request(actor, request_id)

    async def submit(
        self, actor: Actor, package_id: UUID, command: SubmitPackageCommand
    ) -> PackageView:
        return await self.packages.submit(actor, package_id, command)

    async def manager_approve(
        self, actor: Actor, package_id: UUID, command: ApprovalCommand
    ) -> PackageView:
        return await self.packages.manager_approve(actor, package_id, command)

    async def authorise_review(
        self, actor: Actor, artefact_id: UUID, correlation_id: str | None
    ) -> ReleaseAccessRecord:
        return await self.reviews.authorise_review(actor, artefact_id, correlation_id)

    async def review_authorised(
        self,
        actor: Actor,
        access: ReleaseAccessRecord,
        correlation_id: str | None,
    ) -> DownloadStream:
        return await self.reviews.review_authorised(actor, access, correlation_id)

    async def add_managed(
        self, actor: Actor, package_id: UUID, command: ManagedArtefactCreate
    ) -> ManagedArtefactIntent:
        return await self.uploads.add_managed(actor, package_id, command)

    async def add_external(
        self, actor: Actor, package_id: UUID, command: ExternalLinkCreate
    ) -> PackageView:
        return await self.uploads.add_external(actor, package_id, command)

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
        return await self.uploads.upload_content(
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
        return await self.uploads.complete_upload(actor, package_id, intent_id, command)

    async def disseminate(
        self, actor: Actor, package_id: UUID, command: DisseminationCommand
    ) -> PackageView:
        return await self.releases.disseminate(actor, package_id, command)

    async def withdraw(
        self, actor: Actor, package_id: UUID, command: WithdrawalCommand
    ) -> PackageView:
        return await self.releases.withdraw(actor, package_id, command)

    async def customer_release(
        self, actor: Actor, request_id: UUID
    ) -> CustomerReleaseView:
        return await self.customer_access.customer_release(actor, request_id)

    async def find_customer_release(
        self, actor: Actor, request_id: UUID
    ) -> CustomerReleaseView | None:
        return await self.customer_access.find_customer_release(actor, request_id)

    async def accept_product(
        self, actor: Actor, request_id: UUID, command: AcceptanceCommand
    ) -> CustomerReleaseView:
        return await self.customer_access.accept_product(actor, request_id, command)

    async def download(
        self, actor: Actor, artefact_id: UUID, correlation_id: str | None
    ) -> DownloadStream:
        return await self.customer_access.download(actor, artefact_id, correlation_id)

    async def authorise_download(
        self, actor: Actor, artefact_id: UUID, correlation_id: str | None
    ) -> ReleaseAccessRecord:
        return await self.customer_access.authorise_download(
            actor, artefact_id, correlation_id
        )

    async def download_authorised(
        self,
        actor: Actor,
        access: ReleaseAccessRecord,
        correlation_id: str | None,
    ) -> DownloadStream:
        return await self.customer_access.download_authorised(
            actor, access, correlation_id
        )

    async def redirect(
        self, actor: Actor, artefact_id: UUID, correlation_id: str | None
    ) -> str:
        return await self.customer_access.redirect(actor, artefact_id, correlation_id)
