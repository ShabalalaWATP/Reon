"""QC dissemination and withdrawal operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from mist_service.domain import Actor
from mist_service.models import RequestStatus, UserRole
from mist_service.product_errors import ProductConflict, ProductNotFound
from mist_service.product_types import ArtefactKind, PackageStatus
from mist_service.schemas.products import (
    DisseminationCommand,
    PackageView,
    WithdrawalCommand,
)
from mist_service.services.product_repository_port import (
    ProductReleaseServiceRepository,
)
from mist_service.services.product_service_support import ProductServiceSupport


class ProductReleaseService(ProductServiceSupport[ProductReleaseServiceRepository]):
    """Release the latest approved package through a claimed QC task."""

    def __init__(self, repository: ProductReleaseServiceRepository) -> None:
        super().__init__(repository)

    async def disseminate(
        self, actor: Actor, package_id: UUID, command: DisseminationCommand
    ) -> PackageView:
        package, request = await self._authorised_package(actor, package_id, lock=True)
        latest_package = await self._repository.latest_package(request.id)
        if (
            actor.role is not UserRole.QUALITY_RELEASE
            or not await self._repository.live_qc_membership(actor.id, manager=True)
            or request.status != RequestStatus.READY_FOR_RELEASE.value
            or latest_package is None
            or latest_package.id != package.id
            or latest_package.package_version != package.package_version
        ):
            raise ProductNotFound()
        if actor.id in await self._repository.release_excluded_actor_ids(package.id):
            raise ProductNotFound()
        if not await self._repository.release_task_claimed_by(package.id, actor.id):
            raise ProductNotFound()
        view = await self._repository.view(package.id)
        has_links = any(
            item.kind is ArtefactKind.EXTERNAL_LINK for item in view.artefacts
        )
        if (
            package.status is PackageStatus.DISSEMINATED
            and package.package_checksum == command.package_checksum.lower()
            and await self._repository.dissemination_matches(
                package.id, request.requester_id, command.idempotency_key
            )
        ):
            return view
        if package.status is not PackageStatus.MANAGER_APPROVED or (
            has_links and not command.external_link_attested
        ):
            raise ProductNotFound()
        self._expect(package, command.expected_version, command.package_checksum)
        now = datetime.now(UTC)
        if any(
            item.expires_at and self._aware(item.expires_at) <= now
            for item in view.artefacts
        ):
            raise ProductConflict("An external product link has expired.")
        if has_links:
            await self._repository.attest_links(package.id, actor.id, now=now)
        await self._repository.disseminate(
            package.id,
            actor.id,
            request.requester_id,
            command.idempotency_key,
            now=now,
        )
        return await self._repository.view(package.id)

    async def withdraw(
        self, actor: Actor, package_id: UUID, command: WithdrawalCommand
    ) -> PackageView:
        package, _request = await self._authorised_package(actor, package_id, lock=True)
        if (
            actor.role is not UserRole.QUALITY_RELEASE
            or not await self._repository.live_qc_membership(actor.id, manager=True)
            or package.status is not PackageStatus.DISSEMINATED
            or package.version != command.expected_version
        ):
            raise ProductNotFound()
        await self._repository.withdraw(
            package.id, actor.id, command.reason, now=datetime.now(UTC)
        )
        return await self._repository.view(package.id)


# Temporary import compatibility while callers migrate to the focused name.
ProductReleaseOperations = ProductReleaseService
