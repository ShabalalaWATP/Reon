"""Service-request use cases independent of HTTP and SQLAlchemy."""

from __future__ import annotations

import builtins
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
    RequestCancel,
    RequestCreate,
    RequestDetail,
    RequestSummary,
)

REQUESTER_HIDDEN_EVENT_TYPES = frozenset({"task_hastener"})


class RequestRepository(Protocol):
    async def create(
        self,
        actor: Actor,
        command: RequestCreate,
    ) -> RequestDetail: ...

    async def list_for_requester(self, requester_id: UUID) -> list[RequestSummary]: ...

    async def page_for_requester(
        self,
        requester_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[RequestSummary], str | None]: ...

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
        event_limit: int = 50,
        event_cursor: str | None = None,
    ) -> RequestDetail: ...

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

    async def cancel(
        self,
        request_id: UUID,
        actor: Actor,
        command: RequestCancel,
    ) -> RequestDetail: ...


class RequestService:
    """Enforce role and ownership before persistence operations."""

    def __init__(self, repository: RequestRepository) -> None:
        self._repository = repository

    async def create(self, actor: Actor, command: RequestCreate) -> RequestDetail:
        if actor.role != UserRole.REQUESTER:
            raise ObjectNotFound()
        return await self._repository.create(actor, command)

    async def list(self, actor: Actor) -> list[RequestSummary]:
        if actor.role != UserRole.REQUESTER:
            raise ObjectNotFound()
        return await self._repository.list_for_requester(actor.id)

    async def list_page(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[builtins.list[RequestSummary], str | None]:
        if actor.role != UserRole.REQUESTER:
            raise ObjectNotFound()
        return await self._repository.page_for_requester(
            actor.id, limit=limit, cursor=cursor
        )

    async def get(self, actor: Actor, request_id: UUID) -> RequestDetail:
        return await self._get(actor, request_id)

    async def get_page(
        self,
        actor: Actor,
        request_id: UUID,
        *,
        event_limit: int = 50,
        event_cursor: str | None = None,
    ) -> RequestDetail:
        return await self._get(
            actor,
            request_id,
            event_limit=event_limit,
            event_cursor=event_cursor,
        )

    async def _get(
        self,
        actor: Actor,
        request_id: UUID,
        *,
        event_limit: int | None = None,
        event_cursor: str | None = None,
    ) -> RequestDetail:
        record = await self._repository.get_record_for_actor(
            request_id, actor, lock=True
        )
        if record is None or not can_view_request(actor, record):
            raise ObjectNotFound()
        reveal = actor.role != UserRole.REQUESTER
        clarifications = actor.role in {
            UserRole.REQUESTER,
            UserRole.DELIVERY_SPECIALIST,
            UserRole.DELIVERY_TEAM_LEAD,
        }
        if event_limit is None:
            detail = await self._repository.get_detail(
                request_id,
                reveal_unreleased_deliverable=reveal,
                include_clarifications=clarifications,
            )
        else:
            detail = await self._repository.get_detail(
                request_id,
                reveal_unreleased_deliverable=reveal,
                include_clarifications=clarifications,
                event_limit=event_limit,
                event_cursor=event_cursor,
            )
        if actor.role is not UserRole.REQUESTER:
            return detail
        visible_events = [
            event
            for event in detail.events
            if event.type not in REQUESTER_HIDDEN_EVENT_TYPES
        ]
        if len(visible_events) == len(detail.events):
            return detail
        return detail.model_copy(
            update={"events": visible_events}
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

    async def cancel(
        self,
        actor: Actor,
        request_id: UUID,
        command: RequestCancel,
    ) -> RequestDetail:
        record = await self._repository.get_record_for_actor(
            request_id, actor, lock=True
        )
        if (
            record is None
            or actor.role is not UserRole.REQUESTER
            or record.requester_id != actor.id
        ):
            raise ObjectNotFound()
        return await self._repository.cancel(request_id, actor, command)

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
