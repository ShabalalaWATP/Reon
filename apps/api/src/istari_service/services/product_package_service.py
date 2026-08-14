"""Managed-product package authoring and review-state lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from istari_service.domain import Actor
from istari_service.models import RequestStatus, UserRole
from istari_service.policies import has_self_request_conflict
from istari_service.product_errors import (
    ProductConflict,
    ProductNotFound,
    ProductValidationFailed,
)
from istari_service.product_package_policy import validate_covering_note
from istari_service.product_security import MAX_PACKAGE_BYTES
from istari_service.product_types import (
    PackageRecord,
    PackageStatus,
    ProductRequestRecord,
)
from istari_service.schemas.products import (
    ApprovalCommand,
    PackageCreate,
    PackageView,
    SubmitPackageCommand,
)
from istari_service.services.product_repository_port import (
    ProductPackageServiceRepository,
)
from istari_service.services.product_service_support import ProductServiceSupport


class ProductPackageService(ProductServiceSupport[ProductPackageServiceRepository]):
    """Create, inspect, submit and manager-approve product packages."""

    def __init__(
        self,
        repository: ProductPackageServiceRepository,
        *,
        maximum_package_bytes: int = MAX_PACKAGE_BYTES,
    ) -> None:
        super().__init__(repository)
        self._maximum_package_bytes = maximum_package_bytes

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
        if not await self._can_review(actor, package, request):
            raise ProductNotFound()
        return await self._repository.view(
            package.id,
            include_review_details=await self._can_inspect(actor, package, request),
        )

    async def get_package_for_request(
        self, actor: Actor, request_id: UUID
    ) -> PackageView | None:
        request = await self._repository.request(request_id, lock=False)
        if (
            request is None
            or has_self_request_conflict(actor, request)
            or not await self._repository.active_actor(actor)
            or not await self._can_review_request(actor, request)
        ):
            raise ProductNotFound()
        package = await self._repository.latest_package(request_id)
        if package is None:
            return None
        return await self.get_package(actor, package.id)

    async def submit(
        self, actor: Actor, package_id: UUID, command: SubmitPackageCommand
    ) -> PackageView:
        package, _request = await self._editable(
            actor, package_id, command.expected_version
        )
        covering_note = validate_covering_note(
            package.policy_version, command.covering_note
        )
        checksum, count, total_size = await self._repository.package_digest(
            package.id, covering_note
        )
        if not 1 <= count <= 10 or total_size < 0:
            raise ProductConflict("Every artefact must pass validation before review.")
        if total_size > self._maximum_package_bytes:
            raise ProductValidationFailed(
                "The product package exceeds the configured limit."
            )
        await self._repository.freeze(package.id, checksum, covering_note)
        return await self._repository.view(package.id)

    async def manager_approve(
        self, actor: Actor, package_id: UUID, command: ApprovalCommand
    ) -> PackageView:
        package, request = await self._authorised_package(actor, package_id, lock=True)
        if (
            actor.role is not UserRole.DELIVERY_TEAM_LEAD
            or not await self._repository.live_delivery_membership(
                actor.id,
                request.assigned_team_id,
                request.assigned_team,
                manager=True,
            )
            or request.status != RequestStatus.LEAD_REVIEW.value
            or package.author_user_id == actor.id
            or package.status is not PackageStatus.REVIEW_READY
        ):
            raise ProductNotFound()
        if not await self._repository.manager_task_claimed_by(package.id, actor.id):
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
            or has_self_request_conflict(actor, request)
            or not await self._repository.active_actor(actor)
            or actor.role is not UserRole.DELIVERY_SPECIALIST
            or not self._assigned_analyst(actor, request)
            or not await self._repository.live_delivery_membership(
                actor.id,
                request.assigned_team_id,
                request.assigned_team,
                manager=False,
            )
            or request.status
            not in {
                RequestStatus.IN_PROGRESS.value,
                RequestStatus.REWORK_REQUIRED.value,
            }
        ):
            raise ProductNotFound()
        return request

    async def _can_review(
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
            return await self._repository.live_delivery_membership(
                actor.id,
                request.assigned_team_id,
                request.assigned_team,
                manager=True,
            )
        return (
            actor.role is UserRole.QUALITY_RELEASE
            and await self._repository.live_qc_manager(actor.id)
        )

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

    async def _can_review_request(
        self, actor: Actor, request: ProductRequestRecord
    ) -> bool:
        if actor.role is UserRole.DELIVERY_SPECIALIST:
            return self._assigned_analyst(
                actor, request
            ) and await self._repository.live_delivery_membership(
                actor.id,
                request.assigned_team_id,
                request.assigned_team,
                manager=False,
            )
        if actor.role is UserRole.DELIVERY_TEAM_LEAD:
            return await self._repository.live_delivery_membership(
                actor.id,
                request.assigned_team_id,
                request.assigned_team,
                manager=True,
            )
        return (
            actor.role is UserRole.QUALITY_RELEASE
            and await self._repository.live_qc_manager(actor.id)
        )
