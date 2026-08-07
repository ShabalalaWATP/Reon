"""Service-request use cases independent of HTTP and SQLAlchemy."""

from __future__ import annotations

import re
from typing import Protocol
from uuid import UUID

from istari_service.domain import Actor, ProductDownload, RequestRecord
from istari_service.errors import FeedbackUnavailable, ObjectNotFound
from istari_service.models import RequestStatus, UserRole
from istari_service.policies import can_view_request
from istari_service.schemas.requests import (
    FeedbackCreate,
    FeedbackView,
    RequestCreate,
    RequestDetail,
    RequestSummary,
)


class RequestRepository(Protocol):
    async def create(
        self,
        actor: Actor,
        command: RequestCreate,
    ) -> RequestDetail: ...

    async def list_for_requester(self, requester_id: UUID) -> list[RequestSummary]: ...

    async def get_record_for_actor(
        self,
        request_id: UUID,
        actor: Actor,
        *,
        lock: bool = False,
    ) -> RequestRecord | None: ...

    async def get_detail(
        self,
        request_id: UUID,
        *,
        reveal_unreleased_deliverable: bool,
        include_clarifications: bool = False,
    ) -> RequestDetail: ...

    async def feedback_exists(self, request_id: UUID) -> bool: ...

    async def get_released_product(
        self,
        request_id: UUID,
        requester_id: UUID,
    ) -> ProductDownload | None: ...

    async def add_feedback(
        self,
        request_id: UUID,
        actor: Actor,
        command: FeedbackCreate,
    ) -> FeedbackView: ...


class RequestService:
    """Enforce role and ownership before persistence operations."""

    def __init__(self, repository: RequestRepository) -> None:
        self._repository = repository

    async def create(self, actor: Actor, command: RequestCreate) -> RequestDetail:
        if (
            actor.role != UserRole.REQUESTER
            or command.requesting_business_area != actor.scope
        ):
            raise ObjectNotFound()
        return await self._repository.create(actor, command)

    async def list(self, actor: Actor) -> list[RequestSummary]:
        if actor.role != UserRole.REQUESTER:
            raise ObjectNotFound()
        return await self._repository.list_for_requester(actor.id)

    async def get(self, actor: Actor, request_id: UUID) -> RequestDetail:
        record = await self._repository.get_record_for_actor(
            request_id, actor, lock=True
        )
        if record is None or not can_view_request(actor, record):
            raise ObjectNotFound()
        return await self._repository.get_detail(
            request_id,
            reveal_unreleased_deliverable=actor.role != UserRole.REQUESTER,
            include_clarifications=actor.role
            in {
                UserRole.REQUESTER,
                UserRole.DELIVERY_SPECIALIST,
                UserRole.DELIVERY_TEAM_LEAD,
            },
        )

    async def add_feedback(
        self,
        actor: Actor,
        request_id: UUID,
        command: FeedbackCreate,
    ) -> FeedbackView:
        record = await self._repository.get_record_for_actor(request_id, actor)
        if (
            record is None
            or actor.role != UserRole.REQUESTER
            or record.requester_id != actor.id
        ):
            raise ObjectNotFound()
        if record.status != RequestStatus.COMPLETED:
            raise FeedbackUnavailable()
        return await self._repository.add_feedback(request_id, actor, command)

    async def download_product(
        self,
        actor: Actor,
        request_id: UUID,
    ) -> tuple[str, str]:
        if actor.role is not UserRole.REQUESTER:
            raise ObjectNotFound()
        product = await self._repository.get_released_product(request_id, actor.id)
        if product is None:
            raise ObjectNotFound()
        safe_reference = re.sub(r"[^A-Za-z0-9_-]", "_", product.reference).strip("_")
        filename = f"{safe_reference or request_id}-service-product.txt"
        return filename, product.text
