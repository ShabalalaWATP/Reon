"""Dissemination, acceptance, replacement and withdrawal persistence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

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
from istari_service.repositories.product_lifecycle_events import (
    ProductLifecycleEventMixin,
    package_record,
)


class ProductReleaseLifecycleMixin(ProductLifecycleEventMixin):
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
            return package_record(package)
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
        return package_record(package)

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
            return package_record(package)
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
        return package_record(package)

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
            package,
            "PRODUCT_WITHDRAWN",
            "Managed product withdrawn.",
            actor_id,
        )
        return package_record(package)

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
