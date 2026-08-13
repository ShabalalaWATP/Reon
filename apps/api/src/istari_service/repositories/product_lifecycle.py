"""Review, dissemination, withdrawal and Customer access persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.models import ServiceRequest
from istari_service.product_errors import ProductConflict, ProductNotFound
from istari_service.product_models import (
    ExternalProductLink,
    ProductArtefact,
    ProductDissemination,
    ProductPackage,
)
from istari_service.product_types import (
    ArtefactLifecycle,
    PackageRecord,
    PackageStatus,
)
from istari_service.repositories.event_store import append_request_event
from istari_service.repositories.product_access_repository import (
    ProductAccessRepositoryMixin,
)
from istari_service.request_event_audience import RequestEventAudience


def _package_record(package: ProductPackage) -> PackageRecord:
    return PackageRecord(
        id=package.id,
        request_id=package.request_id,
        author_user_id=package.author_user_id,
        status=package.status,
        package_checksum=package.package_checksum,
        version=package.version,
        package_version=package.package_version,
    )


class ProductLifecycleMixin(ProductAccessRepositoryMixin):
    session: AsyncSession

    async def freeze(self, package_id: UUID, checksum: str) -> PackageRecord:
        package = await self.session.get(ProductPackage, package_id)
        if package is None:
            raise ProductNotFound()
        package.status = PackageStatus.REVIEW_READY
        package.package_checksum = checksum
        package.version += 1
        await self._event(
            package,
            "PRODUCT_SUBMITTED",
            "Product package submitted for review.",
        )
        return _package_record(package)

    async def package_digest(self, package_id: UUID) -> tuple[str, int, int]:
        rows = (
            await self.session.execute(
                select(ProductArtefact, ExternalProductLink)
                .outerjoin(
                    ExternalProductLink,
                    ExternalProductLink.artefact_id == ProductArtefact.id,
                )
                .where(ProductArtefact.package_id == package_id)
                .order_by(ProductArtefact.position)
            )
        ).all()
        serialised = [self._digest_item(item, link) for item, link in rows]
        total_size = sum(item.size_bytes or 0 for item, _link in rows)
        all_clean = all(
            item.lifecycle is ArtefactLifecycle.CLEAN for item, _link in rows
        )
        digest = hashlib.sha256(
            json.dumps(serialised, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return digest, len(rows), total_size if all_clean else -1

    async def approve(
        self, package_id: UUID, actor_id: UUID, *, now: datetime
    ) -> PackageRecord:
        package = await self.session.get(ProductPackage, package_id)
        if package is None:
            raise ProductNotFound()
        package.status = PackageStatus.MANAGER_APPROVED
        package.manager_approved_by_user_id = actor_id
        package.manager_approved_at = now
        package.version += 1
        await self._event(
            package,
            "MANAGER_REVIEW_APPROVED",
            "Manager approved the immutable product package.",
            actor_id,
        )
        return _package_record(package)

    async def disseminate(
        self,
        package_id: UUID,
        actor_id: UUID,
        recipient_id: UUID,
        idempotency_key: UUID,
        *,
        now: datetime,
    ) -> PackageRecord:
        package = await self.session.get(ProductPackage, package_id)
        if package is None or package.package_checksum is None:
            raise ProductNotFound()
        existing = await self.session.scalar(
            select(ProductDissemination).where(
                ProductDissemination.idempotency_key == idempotency_key
            )
        )
        if existing:
            if (
                existing.package_id != package_id
                or existing.recipient_user_id != recipient_id
            ):
                raise ProductNotFound()
            return _package_record(package)
        await self._replace_earlier(package, actor_id)
        package.status = PackageStatus.DISSEMINATED
        package.disseminated_by_user_id = actor_id
        package.disseminated_at = now
        package.version += 1
        await self._set_artefact_lifecycle(package.id, ArtefactLifecycle.RELEASED)
        self.session.add(
            ProductDissemination(
                package_id=package.id,
                recipient_user_id=recipient_id,
                disseminated_by_user_id=actor_id,
                idempotency_key=idempotency_key,
                package_checksum=package.package_checksum,
            )
        )
        await self._event(
            package,
            "PRODUCT_DISSEMINATED",
            "Managed product disseminated to the originating Customer.",
            actor_id,
        )
        return _package_record(package)

    async def dissemination_matches(
        self, package_id: UUID, recipient_id: UUID, idempotency_key: UUID
    ) -> bool:
        match = await self.session.scalar(
            select(ProductDissemination.id).where(
                ProductDissemination.package_id == package_id,
                ProductDissemination.recipient_user_id == recipient_id,
                ProductDissemination.idempotency_key == idempotency_key,
            )
        )
        return match is not None

    async def accept(
        self,
        package_id: UUID,
        recipient_id: UUID,
        idempotency_key: UUID,
        *,
        now: datetime,
    ) -> PackageRecord:
        package = await self.session.get(ProductPackage, package_id)
        dissemination = await self.session.scalar(
            select(ProductDissemination)
            .where(
                ProductDissemination.package_id == package_id,
                ProductDissemination.recipient_user_id == recipient_id,
                ProductDissemination.withdrawn_at.is_(None),
            )
            .with_for_update()
        )
        if (
            package is None
            or package.status is not PackageStatus.DISSEMINATED
            or dissemination is None
        ):
            raise ProductNotFound()
        if dissemination.accepted_at is not None:
            if dissemination.acceptance_key != idempotency_key:
                raise ProductConflict("The product has already been accepted.")
            return _package_record(package)
        reused = await self.session.scalar(
            select(ProductDissemination.id).where(
                ProductDissemination.acceptance_key == idempotency_key
            )
        )
        if reused is not None:
            raise ProductNotFound()
        dissemination.accepted_at = now
        dissemination.acceptance_key = idempotency_key
        await self._event(
            package,
            "PRODUCT_ACCEPTED",
            "Customer accepted the disseminated product.",
            recipient_id,
        )
        return _package_record(package)

    async def attest_links(
        self, package_id: UUID, actor_id: UUID, *, now: datetime
    ) -> None:
        links = (
            await self.session.scalars(
                select(ExternalProductLink)
                .join(ProductArtefact)
                .where(ProductArtefact.package_id == package_id)
            )
        ).all()
        for link in links:
            link.qc_attested = True
            link.approved_by_user_id = actor_id
            link.approved_at = now

    async def withdraw(
        self, package_id: UUID, actor_id: UUID, reason: str, *, now: datetime
    ) -> PackageRecord:
        package = await self.session.get(ProductPackage, package_id)
        if package is None:
            raise ProductNotFound()
        package.status = PackageStatus.WITHDRAWN
        package.withdrawn_at = now
        package.withdrawal_reason = reason
        package.version += 1
        await self._set_artefact_lifecycle(package.id, ArtefactLifecycle.WITHDRAWN)
        dissemination = await self.session.scalar(
            select(ProductDissemination).where(
                ProductDissemination.package_id == package.id
            )
        )
        if dissemination is not None:
            dissemination.withdrawn_at = now
        await self._event(
            package, "PRODUCT_WITHDRAWN", "Managed product withdrawn.", actor_id
        )
        return _package_record(package)

    async def _replace_earlier(self, package: ProductPackage, actor_id: UUID) -> None:
        earlier = (
            await self.session.scalars(
                select(ProductPackage)
                .where(
                    ProductPackage.request_id == package.request_id,
                    ProductPackage.status == PackageStatus.DISSEMINATED,
                    ProductPackage.id != package.id,
                )
                .with_for_update()
            )
        ).all()
        for old in earlier:
            old.status = PackageStatus.REPLACED
            old.version += 1
            await self._set_artefact_lifecycle(old.id, ArtefactLifecycle.REPLACED)
            await self._event(
                old,
                "PRODUCT_REPLACED",
                "An earlier managed product was replaced.",
                actor_id,
            )

    async def _set_artefact_lifecycle(
        self, package_id: UUID, lifecycle: ArtefactLifecycle
    ) -> None:
        artefacts = (
            await self.session.scalars(
                select(ProductArtefact).where(ProductArtefact.package_id == package_id)
            )
        ).all()
        for artefact in artefacts:
            artefact.lifecycle = lifecycle
            artefact.version += 1

    async def _event(
        self,
        package: ProductPackage,
        event_type: str,
        message: str,
        actor_id: UUID | None = None,
    ) -> None:
        request = await self.session.get(ServiceRequest, package.request_id)
        if request:
            await append_request_event(
                self.session,
                request_id=request.id,
                actor_id=actor_id or package.author_user_id,
                event_type=event_type,
                message=message,
                prior_status=request.status,
                next_status=request.status,
                audience=(
                    RequestEventAudience.CUSTOMER_AND_STAFF
                    if event_type
                    in {
                        "PRODUCT_DISSEMINATED",
                        "PRODUCT_ACCEPTED",
                        "PRODUCT_WITHDRAWN",
                        "PRODUCT_REPLACED",
                    }
                    else RequestEventAudience.STAFF_ONLY
                ),
                details={
                    "packageId": str(package.id),
                    "packageVersion": package.package_version,
                },
            )

    @staticmethod
    def _digest_item(
        item: ProductArtefact, link: ExternalProductLink | None
    ) -> dict[str, object]:
        return {
            "position": item.position,
            "kind": item.kind.value,
            "label": item.label,
            "filename": item.filename,
            "mediaType": item.media_type,
            "size": item.size_bytes,
            "checksum": item.checksum,
            "destination": link.destination_url if link else None,
            "expiresAt": (
                link.expires_at.isoformat() if link and link.expires_at else None
            ),
        }
