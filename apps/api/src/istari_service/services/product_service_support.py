"""Shared policy and dependencies for managed-product use cases."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID

from istari_service.domain import Actor
from istari_service.models import UserRole
from istari_service.product_errors import (
    ProductConflict,
    ProductDependencyUnavailable,
    ProductNotFound,
)
from istari_service.product_ports import (
    DocumentScanner,
    ExternalLinkPolicy,
    PrivateObjectStorage,
    ProductAccessAudit,
)
from istari_service.product_security import (
    MAX_FILE_BYTES,
    MAX_PACKAGE_BYTES,
    AllowedHttpsLinkPolicy,
)
from istari_service.product_types import (
    PackageRecord,
    PackageStatus,
    ProductRequestRecord,
)
from istari_service.services.product_repository_port import ProductRepository


class ProductServiceSupport:
    def __init__(
        self,
        repository: ProductRepository,
        storage: PrivateObjectStorage,
        scanner: DocumentScanner,
        link_policy: ExternalLinkPolicy,
        access_audit: ProductAccessAudit,
        *,
        upload_ttl: timedelta = timedelta(minutes=10),
        maximum_file_bytes: int = MAX_FILE_BYTES,
        maximum_package_bytes: int = MAX_PACKAGE_BYTES,
        managed_file_uploads_enabled: bool = True,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._scanner = scanner
        self._link_policy = link_policy
        self._audit = access_audit
        self._upload_ttl = upload_ttl
        self._maximum_file_bytes = maximum_file_bytes
        self._maximum_package_bytes = maximum_package_bytes
        self._managed_file_uploads_enabled = managed_file_uploads_enabled

    def _require_managed_file_uploads(self) -> None:
        if not self._managed_file_uploads_enabled:
            raise ProductDependencyUnavailable(
                "Managed-file uploads are unavailable in this environment."
            )

    async def _editable(
        self, actor: Actor, package_id: UUID, expected_version: int
    ) -> tuple[PackageRecord, ProductRequestRecord]:
        package, request = await self._authorised_package(actor, package_id, lock=True)
        self._require_draft_author(actor, package, request)
        if package.version != expected_version:
            raise ProductConflict()
        return package, request

    @staticmethod
    def _require_draft_author(
        actor: Actor, package: PackageRecord, request: ProductRequestRecord
    ) -> None:
        if (
            package.status is not PackageStatus.DRAFT
            or package.author_user_id != actor.id
            or actor.role is not UserRole.DELIVERY_SPECIALIST
            or request.assigned_specialist_id != actor.id
            or not ProductServiceSupport._assigned_team(actor, request)
        ):
            raise ProductConflict()

    @staticmethod
    def _assigned_team(actor: Actor, request: ProductRequestRecord) -> bool:
        if request.assigned_team_id is not None:
            return request.assigned_team_id in actor.organisation_unit_ids
        return request.assigned_team == actor.scope

    async def _authorised_package(
        self, actor: Actor, package_id: UUID, *, lock: bool
    ) -> tuple[PackageRecord, ProductRequestRecord]:
        package = await self._repository.package(package_id, lock=lock)
        if package is None or not await self._repository.active_actor(actor):
            raise ProductNotFound()
        request = await self._repository.request(package.request_id, lock=lock)
        if request is None:
            raise ProductNotFound()
        return package, request

    @staticmethod
    def _expect(package: PackageRecord, version: int, checksum: str) -> None:
        if (
            package.version != version
            or package.package_checksum is None
            or not hmac.compare_digest(package.package_checksum, checksum.lower())
        ):
            raise ProductConflict()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def _approved_link(
        self, request_id: UUID, destination: str
    ) -> tuple[str, str]:
        environment_destination, environment_domain = self._link_policy.normalise(
            destination
        )
        pinned_domains = await self._repository.approved_link_domains(request_id)
        pinned_destination, pinned_domain = AllowedHttpsLinkPolicy(
            pinned_domains or frozenset()
        ).normalise(environment_destination)
        if pinned_domain != environment_domain:
            raise ProductNotFound()
        return pinned_destination, pinned_domain

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
