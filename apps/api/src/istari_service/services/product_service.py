"""Managed-product package creation and immutable review lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from istari_service.domain import Actor
from istari_service.models import RequestStatus, UserRole
from istari_service.product_errors import (
    ProductConflict,
    ProductNotFound,
    ProductValidationFailed,
)
from istari_service.product_types import (
    PackageRecord,
    PackageStatus,
    ProductRequestRecord,
)
from istari_service.schemas.products import (
    ApprovalCommand,
    PackageCreate,
    PackageView,
    VersionCommand,
)
from istari_service.services.product_release_service import ProductReleaseOperations
from istari_service.services.product_upload_service import ProductUploadOperations


class ProductService(ProductUploadOperations, ProductReleaseOperations):
    """Enforce exact actor, object, state, version and checksum authority."""

    async def create_package(self, actor: Actor, command: PackageCreate) -> PackageView:
        request = await self._author_request(actor, command.request_id)
        if request.version != command.expected_version:
            raise ProductConflict()
        package = await self._repository.create_package(
            request.id, actor.id, command.idempotency_key
        )
        return await self._repository.view(package.id)

    async def get_package(self, actor: Actor, package_id: UUID) -> PackageView:
        package, request = await self._authorised_package(actor, package_id, lock=False)
        if not self._can_review(actor, package, request):
            raise ProductNotFound()
        return await self._repository.view(package.id)

    async def get_package_for_request(
        self, actor: Actor, request_id: UUID
    ) -> PackageView:
        package = await self._repository.latest_package(request_id)
        if package is None:
            raise ProductNotFound()
        return await self.get_package(actor, package.id)

    async def submit(
        self, actor: Actor, package_id: UUID, command: VersionCommand
    ) -> PackageView:
        package, _request = await self._editable(
            actor, package_id, command.expected_version
        )
        checksum, count, total_size = await self._repository.package_digest(package.id)
        if not 1 <= count <= 10 or total_size < 0:
            raise ProductConflict("Every artefact must pass validation before review.")
        if total_size > self._maximum_package_bytes:
            raise ProductValidationFailed(
                "The product package exceeds the configured limit."
            )
        await self._repository.freeze(package.id, checksum)
        return await self._repository.view(package.id)

    async def manager_approve(
        self, actor: Actor, package_id: UUID, command: ApprovalCommand
    ) -> PackageView:
        package, request = await self._authorised_package(actor, package_id, lock=True)
        if (
            actor.role is not UserRole.DELIVERY_TEAM_LEAD
            or not self._assigned_team(actor, request)
            or request.status != RequestStatus.LEAD_REVIEW.value
            or package.author_user_id == actor.id
            or package.status is not PackageStatus.REVIEW_READY
        ):
            raise ProductNotFound()
        self._expect(package, command.expected_version, command.package_checksum)
        await self._repository.approve(package.id, actor.id, now=datetime.now(UTC))
        return await self._repository.view(package.id)

    async def _author_request(
        self, actor: Actor, request_id: UUID
    ) -> ProductRequestRecord:
        request = await self._repository.request(request_id, lock=True)
        if (
            request is None
            or not await self._repository.active_actor(actor)
            or actor.role is not UserRole.DELIVERY_SPECIALIST
            or not self._assigned_analyst(actor, request)
            or not self._assigned_team(actor, request)
            or request.status
            not in {
                RequestStatus.IN_PROGRESS.value,
                RequestStatus.REWORK_REQUIRED.value,
            }
        ):
            raise ProductNotFound()
        return request

    def _can_review(
        self, actor: Actor, package: PackageRecord, request: ProductRequestRecord
    ) -> bool:
        return (
            (
                actor.role is UserRole.DELIVERY_SPECIALIST
                and package.author_user_id == actor.id
                and self._assigned_analyst(actor, request)
            )
            or (
                actor.role is UserRole.DELIVERY_TEAM_LEAD
                and self._assigned_team(actor, request)
            )
            or actor.role is UserRole.QUALITY_RELEASE
        )

    @staticmethod
    def _assigned_analyst(actor: Actor, request: ProductRequestRecord) -> bool:
        return request.assigned_specialist_id == actor.id or (
            actor.id in request.participant_ids
        )
