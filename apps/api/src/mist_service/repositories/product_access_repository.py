"""Customer-scoped released-product read persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.identity_context import customer_context_entitlement
from mist_service.models import RequestStatus, ServiceRequest, User
from mist_service.product_models import (
    ExternalProductLink,
    ProductArtefact,
    ProductDissemination,
    ProductPackage,
)
from mist_service.product_types import (
    ArtefactLifecycle,
    PackageStatus,
    ReleaseAccessRecord,
)
from mist_service.repositories.product_records import artefact_record
from mist_service.repositories.product_views import customer_release_view
from mist_service.schemas.products import CustomerReleaseView


class ProductAccessRepositoryMixin:
    session: AsyncSession

    async def release_view(
        self, request_id: UUID, requester_id: UUID
    ) -> CustomerReleaseView | None:
        package = await self._released_package(request_id, requester_id)
        return await customer_release_view(self.session, package) if package else None

    async def access(
        self, artefact_id: UUID, requester_id: UUID
    ) -> ReleaseAccessRecord | None:
        row = (
            await self.session.execute(
                select(
                    ProductArtefact,
                    ProductPackage,
                    ServiceRequest,
                    ExternalProductLink,
                )
                .select_from(ProductArtefact)
                .join(
                    ProductPackage,
                    ProductPackage.id == ProductArtefact.package_id,
                )
                .join(
                    ServiceRequest,
                    ServiceRequest.id == ProductPackage.request_id,
                )
                .join(
                    ProductDissemination,
                    ProductDissemination.package_id == ProductPackage.id,
                )
                .join(User, User.id == ServiceRequest.requester_id)
                .outerjoin(
                    ExternalProductLink,
                    ExternalProductLink.artefact_id == ProductArtefact.id,
                )
                .where(
                    ProductArtefact.id == artefact_id,
                    ProductArtefact.lifecycle == ArtefactLifecycle.RELEASED,
                    ProductPackage.status == PackageStatus.DISSEMINATED,
                    ServiceRequest.requester_id == requester_id,
                    ServiceRequest.status == RequestStatus.COMPLETED,
                    ProductDissemination.recipient_user_id == requester_id,
                    ProductDissemination.withdrawn_at.is_(None),
                    ProductDissemination.package_checksum
                    == ProductPackage.package_checksum,
                    User.is_active.is_(True),
                    customer_context_entitlement(),
                )
            )
        ).one_or_none()
        return (
            ReleaseAccessRecord(
                request_id=row[2].id,
                package_id=row[1].id,
                artefact=artefact_record(row[0], row[3]),
            )
            if row
            else None
        )

    async def _released_package(
        self, request_id: UUID, requester_id: UUID
    ) -> ProductPackage | None:
        package: ProductPackage | None = await self.session.scalar(
            select(ProductPackage)
            .select_from(ProductPackage)
            .join(
                ServiceRequest,
                ServiceRequest.id == ProductPackage.request_id,
            )
            .join(
                ProductDissemination,
                ProductDissemination.package_id == ProductPackage.id,
            )
            .join(User, User.id == ServiceRequest.requester_id)
            .where(
                ProductPackage.request_id == request_id,
                ProductPackage.status == PackageStatus.DISSEMINATED,
                ServiceRequest.requester_id == requester_id,
                ServiceRequest.status == RequestStatus.COMPLETED,
                ProductDissemination.recipient_user_id == requester_id,
                ProductDissemination.withdrawn_at.is_(None),
                ProductDissemination.package_checksum
                == ProductPackage.package_checksum,
                User.is_active.is_(True),
                customer_context_entitlement(),
            )
        )
        return package
