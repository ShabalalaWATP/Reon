"""Narrow application ports for request coordination."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from istari_service.domain import Actor
from istari_service.models import RequestStatus, ServiceRequest, UserRole
from istari_service.request_event_audience import RequestEventAudience
from istari_service.request_event_models import RequestEvent
from istari_service.schemas.conversations import (
    ConversationMessageCreate,
    ConversationMutationResult,
)


@dataclass(frozen=True, slots=True)
class ReturnRouteTarget:
    """Safe route data required to record an ownership-return request."""

    name: str
    position: int


class CoordinationRequestReader(Protocol):
    """Load the request whose coordination boundary is being authorised."""

    async def request(self, request_id: UUID) -> ServiceRequest | None: ...


class CoordinationAccessReader(Protocol):
    """Resolve actor membership and position on the immutable selected route."""

    async def has_route_membership(self, actor: Actor, request_id: UUID) -> bool: ...

    def route_position(self, role: UserRole) -> int | None: ...


class CoordinationReturnReader(Protocol):
    """Resolve an allowed return target from the request's selected route."""

    async def route_target(
        self, request_id: UUID, unit_id: UUID
    ) -> ReturnRouteTarget | None: ...


class CoordinationEventWriter(Protocol):
    """Append one immutable event to a request audit chain."""

    async def append(
        self,
        *,
        request_id: UUID,
        actor_id: UUID | None,
        event_type: str,
        message: str,
        prior_status: RequestStatus | None,
        next_status: RequestStatus | None,
        audience: RequestEventAudience | None = None,
        details: Mapping[str, object] | None = None,
    ) -> RequestEvent: ...


class CoordinationConversationPoster(Protocol):
    """Post a structured message while preserving the compatibility event."""

    async def post_message(
        self,
        actor: Actor,
        request_id: UUID,
        command: ConversationMessageCreate,
        *,
        legacy_event_message: str | None = None,
        legacy_event_type: str | None = None,
        legacy_event_audience: RequestEventAudience | None = None,
    ) -> ConversationMutationResult: ...
