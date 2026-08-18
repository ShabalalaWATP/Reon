"""Authenticated Customer product access and acceptance operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from mist_service.domain import Actor
from mist_service.models import UserRole
from mist_service.product_errors import (
    ProductDependencyUnavailable,
    ProductNotFound,
    ProductValidationFailed,
)
from mist_service.product_ports import (
    ExternalLinkPolicy,
    PrivateObjectStorage,
    ProductAccessAudit,
)
from mist_service.product_types import (
    AccessKind,
    AccessOutcome,
    ArtefactKind,
    DownloadStream,
    ReleaseAccessRecord,
)
from mist_service.schemas.products import AcceptanceCommand, CustomerReleaseView
from mist_service.services.product_repository_port import (
    ProductCustomerReleaseRepository,
    ProductLinkRepository,
)
from mist_service.services.product_service_collaborators import (
    ProductAccessRecorder,
    ProductLinkAuthoriser,
)


class ProductCustomerReleaseService:
    """Expose only disseminated products owned by the active Customer."""

    def __init__(
        self,
        repository: ProductCustomerReleaseRepository,
        links: ProductLinkRepository,
        storage: PrivateObjectStorage,
        link_policy: ExternalLinkPolicy,
        access_audit: ProductAccessAudit,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._links = ProductLinkAuthoriser(links, link_policy)
        self._access_recorder = ProductAccessRecorder(access_audit)

    async def customer_release(
        self, actor: Actor, request_id: UUID
    ) -> CustomerReleaseView:
        view = await self.find_customer_release(actor, request_id)
        if view is None:
            raise ProductNotFound()
        return view

    async def find_customer_release(
        self, actor: Actor, request_id: UUID
    ) -> CustomerReleaseView | None:
        if (
            actor.role is not UserRole.REQUESTER
            or not await self._repository.active_actor(actor)
        ):
            raise ProductNotFound()
        request = await self._repository.request(request_id, lock=False)
        if request is None or request.requester_id != actor.id:
            raise ProductNotFound()
        return await self._repository.release_view(request_id, actor.id)

    async def accept_product(
        self, actor: Actor, request_id: UUID, command: AcceptanceCommand
    ) -> CustomerReleaseView:
        if (
            actor.role is not UserRole.REQUESTER
            or not await self._repository.active_actor(actor)
        ):
            raise ProductNotFound()
        view = await self._repository.release_view(request_id, actor.id)
        if view is None:
            raise ProductNotFound()
        await self._repository.accept(
            view.package_id,
            actor.id,
            command.idempotency_key,
            now=datetime.now(UTC),
        )
        accepted = await self._repository.release_view(request_id, actor.id)
        if accepted is None:
            raise ProductNotFound()
        return accepted

    async def download(
        self, actor: Actor, artefact_id: UUID, correlation_id: str | None
    ) -> DownloadStream:
        access = await self.authorise_download(actor, artefact_id, correlation_id)
        return await self.download_authorised(actor, access, correlation_id)

    async def authorise_download(
        self,
        actor: Actor,
        artefact_id: UUID,
        correlation_id: str | None,
    ) -> ReleaseAccessRecord:
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
        return access

    async def download_authorised(
        self,
        actor: Actor,
        access: ReleaseAccessRecord,
        correlation_id: str | None,
    ) -> DownloadStream:
        artefact_id, artefact = access.artefact.id, access.artefact
        if (
            not artefact.released_key
            or not artefact.filename
            or not artefact.media_type
        ):
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
            destination, domain = await self._links.approved(
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
        await self._access_recorder.record(
            actor,
            target,
            kind,
            outcome,
            reason,
            correlation_id,
            access,
        )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
