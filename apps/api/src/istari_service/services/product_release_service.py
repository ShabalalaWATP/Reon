"""QC dissemination and authenticated Customer product access."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from istari_service.domain import Actor
from istari_service.models import RequestStatus, UserRole
from istari_service.product_errors import (
    ProductConflict,
    ProductDependencyUnavailable,
    ProductNotFound,
    ProductValidationFailed,
)
from istari_service.product_security import normalise_product_correlation_id
from istari_service.product_types import (
    AccessAuditRecord,
    AccessKind,
    AccessOutcome,
    ArtefactKind,
    DownloadStream,
    PackageStatus,
    ReleaseAccessRecord,
)
from istari_service.schemas.products import (
    CustomerReleaseView,
    DisseminationCommand,
    PackageView,
    WithdrawalCommand,
)
from istari_service.services.product_service_support import ProductServiceSupport


class ProductReleaseOperations(ProductServiceSupport):
    async def disseminate(
        self, actor: Actor, package_id: UUID, command: DisseminationCommand
    ) -> PackageView:
        package, request = await self._authorised_package(actor, package_id, lock=True)
        if (
            actor.role is not UserRole.QUALITY_RELEASE
            or request.status != RequestStatus.READY_FOR_RELEASE.value
        ):
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
            or package.status is not PackageStatus.DISSEMINATED
            or package.version != command.expected_version
        ):
            raise ProductNotFound()
        await self._repository.withdraw(
            package.id, actor.id, command.reason, now=datetime.now(UTC)
        )
        return await self._repository.view(package.id)

    async def customer_release(
        self, actor: Actor, request_id: UUID
    ) -> CustomerReleaseView:
        if (
            actor.role is not UserRole.REQUESTER
            or not await self._repository.active_actor(actor)
        ):
            raise ProductNotFound()
        view = await self._repository.release_view(request_id, actor.id)
        if view is None:
            raise ProductNotFound()
        return view

    async def download(
        self, actor: Actor, artefact_id: UUID, correlation_id: str | None
    ) -> DownloadStream:
        access = await self._customer_access(
            actor, artefact_id, AccessKind.DOWNLOAD, correlation_id
        )
        artefact = access.artefact
        if (
            artefact.kind is not ArtefactKind.MANAGED_FILE
            or not artefact.released_key
            or not artefact.filename
            or not artefact.media_type
        ):
            await self._audit_access(
                actor,
                artefact_id,
                AccessKind.DOWNLOAD,
                AccessOutcome.UNAVAILABLE,
                "WRONG_ARTEFACT_KIND",
                correlation_id,
                access,
            )
            raise ProductNotFound()
        try:
            result = await self._storage.download(
                artefact.released_key,
                filename=artefact.filename,
                media_type=artefact.media_type,
            )
        except ProductDependencyUnavailable:
            await self._audit_access(
                actor,
                artefact_id,
                AccessKind.DOWNLOAD,
                AccessOutcome.UNAVAILABLE,
                "STORAGE_UNAVAILABLE",
                correlation_id,
                access,
            )
            raise
        await self._audit_access(
            actor,
            artefact_id,
            AccessKind.DOWNLOAD,
            AccessOutcome.ALLOWED,
            "CUSTOMER_DOWNLOAD",
            correlation_id,
            access,
        )
        return result

    async def redirect(
        self, actor: Actor, artefact_id: UUID, correlation_id: str | None
    ) -> str:
        access = await self._customer_access(
            actor, artefact_id, AccessKind.REDIRECT, correlation_id
        )
        artefact = access.artefact
        if (
            artefact.kind is not ArtefactKind.EXTERNAL_LINK
            or not artefact.destination_url
            or (
                artefact.expires_at
                and self._aware(artefact.expires_at) <= datetime.now(UTC)
            )
        ):
            await self._audit_access(
                actor,
                artefact_id,
                AccessKind.REDIRECT,
                AccessOutcome.UNAVAILABLE,
                "LINK_UNAVAILABLE",
                correlation_id,
                access,
            )
            raise ProductNotFound()
        try:
            destination, domain = await self._approved_link(
                access.request_id, artefact.destination_url
            )
        except ProductValidationFailed as exc:
            await self._audit_access(
                actor,
                artefact_id,
                AccessKind.REDIRECT,
                AccessOutcome.DENIED,
                "LINK_POLICY_CHANGED",
                correlation_id,
                access,
            )
            raise ProductNotFound() from exc
        if domain != artefact.destination_domain:
            await self._audit_access(
                actor,
                artefact_id,
                AccessKind.REDIRECT,
                AccessOutcome.DENIED,
                "LINK_POLICY_CHANGED",
                correlation_id,
                access,
            )
            raise ProductNotFound()
        await self._audit_access(
            actor,
            artefact_id,
            AccessKind.REDIRECT,
            AccessOutcome.ALLOWED,
            "CUSTOMER_REDIRECT",
            correlation_id,
            access,
        )
        return destination

    async def _customer_access(
        self,
        actor: Actor,
        artefact_id: UUID,
        kind: AccessKind,
        correlation_id: str | None,
    ) -> ReleaseAccessRecord:
        if (
            actor.role is not UserRole.REQUESTER
            or not await self._repository.active_actor(actor)
        ):
            await self._audit_access(
                actor,
                artefact_id,
                kind,
                AccessOutcome.DENIED,
                "ACCESS_DENIED",
                correlation_id,
            )
            raise ProductNotFound()
        access = await self._repository.access(artefact_id, actor.id)
        if access is None:
            await self._audit_access(
                actor,
                artefact_id,
                kind,
                AccessOutcome.DENIED,
                "ACCESS_DENIED",
                correlation_id,
            )
            raise ProductNotFound()
        return access

    async def _audit_access(
        self,
        actor: Actor,
        target: UUID,
        kind: AccessKind,
        outcome: AccessOutcome,
        reason: str,
        correlation_id: str | None,
        access: ReleaseAccessRecord | None = None,
    ) -> None:
        await self._audit.record(
            AccessAuditRecord(
                request_id=access.request_id if access else None,
                package_id=access.package_id if access else None,
                artefact_id=access.artefact.id if access else None,
                target_reference=target,
                actor_id=actor.id,
                kind=kind,
                outcome=outcome,
                reason_code=reason,
                correlation_id=normalise_product_correlation_id(correlation_id),
            )
        )
