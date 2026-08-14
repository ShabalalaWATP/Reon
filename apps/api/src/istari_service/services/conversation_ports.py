"""Narrow application ports for request conversations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol
from uuid import UUID

from istari_service.conversation_models import (
    ConversationTargetType,
    RequestConversation,
    RequestConversationMessage,
)
from istari_service.conversation_page_types import ConversationPage, MessagePage
from istari_service.domain import Actor
from istari_service.models import RequestStatus, ServiceRequest, UserRole
from istari_service.organisation_models import OrganisationUnit
from istari_service.request_event_audience import RequestEventAudience
from istari_service.request_event_models import RequestEvent


class ConversationPageReader(Protocol):
    async def conversations(
        self,
        request_id: UUID,
        *,
        customer_only: bool,
        allowed_targets: set[ConversationTargetType],
        route_unit_ids: set[UUID],
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> ConversationPage: ...

    async def messages(
        self,
        conversation_id: UUID,
        *,
        limit: int,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> MessagePage: ...

    async def message_pages(
        self, conversation_ids: list[UUID], *, limit: int
    ) -> dict[UUID, MessagePage]: ...

    async def unread_counts(
        self, conversation_ids: list[UUID], actor_id: UUID
    ) -> dict[UUID, int]: ...

    async def admission_counts(
        self, request_id: UUID, actor_id: UUID
    ) -> tuple[int, int, int]: ...


class ConversationAccessReader(Protocol):
    async def request(self, request_id: UUID) -> ServiceRequest | None: ...

    async def active_actor(self, actor: Actor) -> bool: ...

    async def is_active_participant(
        self, request: ServiceRequest, actor: Actor
    ) -> bool: ...

    async def is_active_team_manager(
        self, request: ServiceRequest, actor: Actor
    ) -> bool: ...

    async def is_active_qc_manager(self, actor: Actor) -> bool: ...

    async def selected_route(
        self, request_id: UUID
    ) -> list[tuple[OrganisationUnit, int]]: ...

    async def active_participant_ids(self, request: ServiceRequest) -> set[UUID]: ...

    async def active_team_manager_ids(self, team_id: UUID) -> set[UUID]: ...

    async def active_unit_member_ids(
        self, unit_id: UUID, role: UserRole | None = None
    ) -> set[UUID]: ...

    async def active_qc_ids(self) -> set[UUID]: ...


class RouteMembershipReader(Protocol):
    async def has_route_membership(self, actor: Actor, request_id: UUID) -> bool: ...


class ConversationStore(Protocol):
    async def lock_request(self, request_id: UUID) -> ServiceRequest | None: ...

    async def conversation(
        self, request_id: UUID, conversation_id: UUID
    ) -> RequestConversation | None: ...

    async def mutation_message(
        self, sender_id: UUID, client_mutation_id: UUID
    ) -> RequestConversationMessage | None: ...

    async def first_message_id(self, conversation_id: UUID) -> UUID | None: ...

    async def message_in_conversation(
        self, conversation_id: UUID, message_id: UUID
    ) -> RequestConversationMessage | None: ...

    async def add_message(
        self,
        conversation: RequestConversation | None,
        message: RequestConversationMessage,
        recipient_ids: set[UUID],
    ) -> None: ...

    async def mark_read(
        self, conversation_id: UUID, recipient_id: UUID, at: datetime
    ) -> None: ...


class RequestEventWriter(Protocol):
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
