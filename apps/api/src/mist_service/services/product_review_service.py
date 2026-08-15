"""Staff product-artefact review authorisation and retrieval."""

from __future__ import annotations

from uuid import UUID

from mist_service.domain import Actor
from mist_service.models import RequestStatus, UserRole
from mist_service.product_errors import ProductDependencyUnavailable, ProductNotFound
from mist_service.product_ports import PrivateObjectStorage, ProductAccessAudit
from mist_service.product_types import (
    AccessKind,
    AccessOutcome,
    ArtefactKind,
    ArtefactLifecycle,
    DownloadStream,
    PackageRecord,
    ProductRequestRecord,
    ReleaseAccessRecord,
)
from mist_service.services.product_repository_port import (
    ProductPackageServiceRepository,
)
from mist_service.services.product_service_collaborators import (
    ProductAccessRecorder,
    download_fields,
)
from mist_service.services.product_service_support import ProductServiceSupport


class ProductReviewService(ProductServiceSupport[ProductPackageServiceRepository]):
    """Authorise and audit manager, analyst and QC review downloads."""

    def __init__(
        self,
        repository: ProductPackageServiceRepository,
        storage: PrivateObjectStorage,
        access_audit: ProductAccessAudit,
    ) -> None:
        super().__init__(repository)
        self._storage = storage
        self._access_recorder = ProductAccessRecorder(access_audit)

    async def authorise_review(
        self,
        actor: Actor,
        artefact_id: UUID,
        correlation_id: str | None,
    ) -> ReleaseAccessRecord:
        access = await self._repository.review_access(artefact_id)
        if access is None:
            await self._audit_access(
                actor,
                artefact_id,
                AccessOutcome.DENIED,
                "STAFF_REVIEW_ACCESS_DENIED",
                correlation_id,
            )
            raise ProductNotFound()
        try:
            package, request = await self._authorised_package(
                actor, access.package_id, lock=False
            )
        except ProductNotFound:
            await self._audit_access(
                actor,
                artefact_id,
                AccessOutcome.DENIED,
                "STAFF_REVIEW_ACCESS_DENIED",
                correlation_id,
                access,
            )
            raise
        artefact = access.artefact
        if not await self._can_inspect(actor, package, request):
            await self._audit_access(
                actor,
                artefact_id,
                AccessOutcome.DENIED,
                "STAFF_REVIEW_ACCESS_DENIED",
                correlation_id,
                access,
            )
            raise ProductNotFound()
        if (
            artefact.kind is not ArtefactKind.MANAGED_FILE
            or artefact.lifecycle is not ArtefactLifecycle.CLEAN
            or not artefact.released_key
            or not artefact.filename
            or not artefact.media_type
        ):
            await self._audit_access(
                actor,
                artefact_id,
                AccessOutcome.UNAVAILABLE,
                "STAFF_REVIEW_UNAVAILABLE",
                correlation_id,
                access,
            )
            raise ProductNotFound()
        return access

    async def review_authorised(
        self,
        actor: Actor,
        access: ReleaseAccessRecord,
        correlation_id: str | None,
    ) -> DownloadStream:
        artefact_id, artefact = access.artefact.id, access.artefact
        released_key, filename, media_type = download_fields(artefact)
        try:
            result = await self._storage.download(
                released_key,
                filename=filename,
                media_type=media_type,
            )
        except ProductDependencyUnavailable:
            await self._audit_access(
                actor,
                artefact_id,
                AccessOutcome.UNAVAILABLE,
                "STORAGE_UNAVAILABLE",
                correlation_id,
                access,
            )
            raise
        await self._audit_access(
            actor,
            artefact_id,
            AccessOutcome.ALLOWED,
            "STAFF_PRODUCT_REVIEW",
            correlation_id,
            access,
        )
        return result

    async def _can_inspect(
        self, actor: Actor, package: PackageRecord, request: ProductRequestRecord
    ) -> bool:
        if actor.role is UserRole.DELIVERY_SPECIALIST:
            return (
                package.author_user_id == actor.id
                and self._assigned_analyst(actor, request)
                and await self._repository.live_delivery_membership(
                    actor.id,
                    request.assigned_team_id,
                    request.assigned_team,
                    manager=False,
                )
            )
        if actor.role is UserRole.DELIVERY_TEAM_LEAD:
            return (
                request.status == RequestStatus.LEAD_REVIEW.value
                and await self._repository.live_delivery_membership(
                    actor.id,
                    request.assigned_team_id,
                    request.assigned_team,
                    manager=True,
                )
                and await self._repository.manager_task_claimed_by(package.id, actor.id)
            )
        if (
            actor.role is not UserRole.QUALITY_RELEASE
            or not await self._repository.live_qc_manager(actor.id)
        ):
            return False
        if request.status == RequestStatus.QUALITY_REVIEW.value:
            return await self._repository.quality_task_claimed_by(package.id, actor.id)
        if request.status == RequestStatus.READY_FOR_RELEASE.value:
            return await self._repository.release_task_claimed_by(package.id, actor.id)
        return False

    async def _audit_access(
        self,
        actor: Actor,
        target: UUID,
        outcome: AccessOutcome,
        reason: str,
        correlation_id: str | None,
        access: ReleaseAccessRecord | None = None,
    ) -> None:
        await self._access_recorder.record(
            actor,
            target,
            AccessKind.DOWNLOAD,
            outcome,
            reason,
            correlation_id,
            access,
        )
