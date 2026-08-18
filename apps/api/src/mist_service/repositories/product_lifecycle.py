"""Package review persistence composed with the release lifecycle."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from mist_service.product_errors import ProductNotFound
from mist_service.product_models import (
    ExternalProductLink,
    ProductArtefact,
    ProductPackage,
)
from mist_service.product_types import ArtefactLifecycle, PackageRecord, PackageStatus
from mist_service.repositories.product_access_repository import (
    ProductAccessRepositoryMixin,
)
from mist_service.repositories.product_records import package_record
from mist_service.repositories.product_release_accountability import (
    ProductReleaseAccountabilityRepositoryMixin,
)
from mist_service.repositories.product_release_lifecycle import (
    ProductReleaseLifecycleMixin,
)
from mist_service.repositories.product_review_access import (
    ProductReviewAccessRepositoryMixin,
)


class ProductLifecycleMixin(
    ProductReleaseLifecycleMixin,
    ProductReleaseAccountabilityRepositoryMixin,
    ProductReviewAccessRepositoryMixin,
    ProductAccessRepositoryMixin,
):
    async def freeze(
        self, package_id: UUID, checksum: str, covering_note: str | None
    ) -> PackageRecord:
        package = await self.session.get(ProductPackage, package_id)
        if package is None:
            raise ProductNotFound()
        package.status = PackageStatus.REVIEW_READY
        package.covering_note = covering_note
        package.package_checksum = checksum
        package.version += 1
        await self._event(
            package,
            "PRODUCT_SUBMITTED",
            "Product package submitted for review.",
        )
        return package_record(package)

    async def package_digest(
        self, package_id: UUID, covering_note: str | None
    ) -> tuple[str, int, int]:
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
        evidence = {"artefacts": serialised, "coveringNote": covering_note}
        digest = hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
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
        return package_record(package)

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
