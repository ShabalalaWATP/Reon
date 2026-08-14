"""Focused collaborators shared by managed-product use cases."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from istari_service.domain import Actor
from istari_service.product_errors import (
    ProductConflict,
    ProductDependencyUnavailable,
    ProductNotFound,
)
from istari_service.product_ports import ExternalLinkPolicy, ProductAccessAudit
from istari_service.product_quota_policy import (
    MAX_GLOBAL_ACTIVE_INTENTS,
    MAX_PACKAGE_ACTIVE_INTENTS,
    MAX_REQUEST_ACTIVE_INTENTS,
    MAX_USER_ACTIVE_INTENTS,
)
from istari_service.product_security import AllowedHttpsLinkPolicy
from istari_service.product_types import (
    AccessAuditRecord,
    AccessKind,
    AccessOutcome,
    ArtefactRecord,
    PackageRecord,
    ReleaseAccessRecord,
)
from istari_service.services.product_repository_port import (
    ProductAccessRepository,
    ProductUploadRepository,
)


@dataclass(frozen=True, slots=True)
class ProductStorageLimits:
    package_bytes: int
    request_bytes: int
    user_bytes: int
    service_bytes: int


class ProductUploadPolicy:
    """Enforce upload availability, byte quotas and reservation limits."""

    def __init__(
        self,
        repository: ProductUploadRepository,
        limits: ProductStorageLimits,
        *,
        enabled: bool,
    ) -> None:
        self._repository = repository
        self._limits = limits
        self._enabled = enabled

    def require_enabled(self) -> None:
        if not self._enabled:
            raise ProductDependencyUnavailable(
                "Managed-file uploads are unavailable in this environment."
            )

    async def require_capacity(
        self, package: PackageRecord, additional_bytes: int
    ) -> None:
        usage = await self._repository.storage_usage(
            package.id, package.request_id, package.author_user_id
        )
        byte_limits = (
            (usage.package_bytes, self._limits.package_bytes, "package"),
            (usage.request_bytes, self._limits.request_bytes, "request"),
            (usage.user_bytes, self._limits.user_bytes, "user"),
            (usage.service_bytes, self._limits.service_bytes, "service"),
        )
        for used, limit, scope in byte_limits:
            if used + additional_bytes > limit:
                raise ProductConflict(
                    f"The managed-product {scope} storage limit has been reached."
                )
        count_limits = (
            (usage.package_active_intents, MAX_PACKAGE_ACTIVE_INTENTS, "package"),
            (usage.request_active_intents, MAX_REQUEST_ACTIVE_INTENTS, "request"),
            (usage.user_active_intents, MAX_USER_ACTIVE_INTENTS, "user"),
            (usage.service_active_intents, MAX_GLOBAL_ACTIVE_INTENTS, "service"),
        )
        for used, limit, scope in count_limits:
            if used >= limit:
                raise ProductConflict(
                    f"The managed-product {scope} active-upload limit has been reached."
                )


class ProductLinkAuthoriser:
    """Apply the environment and request-pinned external-link policies."""

    def __init__(
        self,
        repository: ProductAccessRepository,
        environment_policy: ExternalLinkPolicy,
    ) -> None:
        self._repository = repository
        self._environment_policy = environment_policy

    async def approved(self, request_id: UUID, destination: str) -> tuple[str, str]:
        environment_destination, environment_domain = (
            self._environment_policy.normalise(destination)
        )
        pinned_domains = await self._repository.approved_link_domains(request_id)
        pinned_destination, pinned_domain = AllowedHttpsLinkPolicy(
            pinned_domains or frozenset()
        ).normalise(environment_destination)
        if pinned_domain != environment_domain:
            raise ProductNotFound()
        return pinned_destination, pinned_domain


class ProductAccessRecorder:
    """Create uniform access evidence without coupling product services together."""

    def __init__(self, audit: ProductAccessAudit) -> None:
        self._audit = audit

    async def record(
        self,
        actor: Actor,
        target: UUID,
        kind: AccessKind,
        outcome: AccessOutcome,
        reason: str,
        correlation_id: str | None,
        access: ReleaseAccessRecord | None = None,
    ) -> None:
        from istari_service.product_security import normalise_product_correlation_id

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


def download_fields(artefact: ArtefactRecord) -> tuple[str, str, str]:
    """Return storage download fields only for a complete managed artefact."""

    if not artefact.released_key or not artefact.filename or not artefact.media_type:
        raise ProductNotFound()
    return artefact.released_key, artefact.filename, artefact.media_type
