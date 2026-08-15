"""Shared policy and dependencies for managed-product use cases."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from uuid import UUID

from mist_service.domain import Actor
from mist_service.models import RequestStatus, UserRole
from mist_service.policies import has_self_request_conflict
from mist_service.product_errors import ProductConflict, ProductNotFound
from mist_service.product_types import (
    PackageRecord,
    PackageStatus,
    ProductRequestRecord,
)
from mist_service.services.product_repository_port import ProductAccessRepository


class ProductServiceSupport[RepositoryT: ProductAccessRepository]:
    def __init__(
        self,
        repository: RepositoryT,
    ) -> None:
        self._repository = repository

    async def _editable(
        self, actor: Actor, package_id: UUID, expected_version: int
    ) -> tuple[PackageRecord, ProductRequestRecord]:
        package, request = await self._authorised_package(actor, package_id, lock=True)
        await self._require_draft_author(actor, package, request)
        if package.version != expected_version:
            raise ProductConflict()
        return package, request

    async def _require_draft_author(
        self, actor: Actor, package: PackageRecord, request: ProductRequestRecord
    ) -> None:
        if (
            package.status is not PackageStatus.DRAFT
            or package.author_user_id != actor.id
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
            raise ProductConflict()

    @staticmethod
    def _assigned_team(actor: Actor, request: ProductRequestRecord) -> bool:
        if request.assigned_team_id is not None:
            return request.assigned_team_id in actor.organisation_unit_ids
        return request.assigned_team == actor.scope

    @staticmethod
    def _assigned_analyst(actor: Actor, request: ProductRequestRecord) -> bool:
        return request.assigned_specialist_id == actor.id or (
            actor.id in request.participant_ids
        )

    async def _authorised_package(
        self, actor: Actor, package_id: UUID, *, lock: bool
    ) -> tuple[PackageRecord, ProductRequestRecord]:
        package = await self._repository.package(package_id, lock=lock)
        if package is None or not await self._repository.active_actor(actor):
            raise ProductNotFound()
        request = await self._repository.request(package.request_id, lock=lock)
        if request is None or has_self_request_conflict(actor, request):
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

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
