"""Authorise and audit non-blocking request coordination."""

from __future__ import annotations

from uuid import UUID

from mist_service.conversation_models import ConversationTargetType
from mist_service.domain import Actor
from mist_service.errors import InvalidAction, ObjectNotFound
from mist_service.models import (
    RequestStatus,
    ServiceRequest,
    UserRole,
)
from mist_service.policies import can_view_request, has_self_request_conflict
from mist_service.request_coordination_ports import (
    CoordinationAccessReader,
    CoordinationConversationPoster,
    CoordinationEventWriter,
    CoordinationRequestReader,
    CoordinationReturnReader,
)
from mist_service.request_event_audience import RequestEventAudience
from mist_service.request_event_models import RequestEvent
from mist_service.schemas.conversations import ConversationMessageCreate
from mist_service.schemas.coordination import (
    CoordinationAudience,
    CoordinationMessageCreate,
    ReturnRequestCreate,
)
from mist_service.schemas.organisation import TrackedRequestEvent

CURRENT_ROUTE_POSITION = {
    RequestStatus.ROUTING_PENDING: 0,
    RequestStatus.TRIAGE_REVIEW: 0,
    RequestStatus.INFORMATION_REQUIRED: 0,
    RequestStatus.COORDINATION_REVIEW: 1,
    RequestStatus.ON_HOLD: 1,
    RequestStatus.ALLOCATION_REVIEW: 2,
    RequestStatus.DELIVERY_PLANNING: 3,
    RequestStatus.IN_PROGRESS: 3,
    RequestStatus.CUSTOMER_INFORMATION_REQUIRED: 3,
    RequestStatus.LEAD_REVIEW: 3,
    RequestStatus.REWORK_REQUIRED: 3,
    RequestStatus.QUALITY_REVIEW: 4,
    RequestStatus.READY_FOR_RELEASE: 4,
    RequestStatus.COMPLETED: 4,
}


class RequestCoordinationService:
    def __init__(
        self,
        requests: CoordinationRequestReader,
        access: CoordinationAccessReader,
        returns: CoordinationReturnReader,
        events: CoordinationEventWriter,
        conversations: CoordinationConversationPoster,
    ) -> None:
        self._requests = requests
        self._access = access
        self._returns = returns
        self._events = events
        self._conversations = conversations

    async def post_message(
        self, actor: Actor, request_id: UUID, command: CoordinationMessageCreate
    ) -> TrackedRequestEvent:
        await self._authorised_request(actor, request_id)
        if (
            actor.role is UserRole.REQUESTER
            and command.audience is not CoordinationAudience.CURRENT_OWNER
        ):
            raise InvalidAction("Customers can send coordination to the current owner.")
        label = (
            "Question for Customer"
            if command.audience is CoordinationAudience.CUSTOMER
            else "Message for current owner"
        )
        result = await self._conversations.post_message(
            actor,
            request_id,
            ConversationMessageCreate(
                body=command.body,
                client_mutation_id=command.client_mutation_id,
                target_type=(
                    ConversationTargetType.CUSTOMER
                    if command.audience is CoordinationAudience.CUSTOMER
                    else ConversationTargetType.CURRENT_OWNER
                ),
            ),
            legacy_event_message=f"{label} recorded.",
            legacy_event_type="COORDINATION_MESSAGE",
            legacy_event_audience=(
                RequestEventAudience.CUSTOMER_AND_STAFF
                if command.audience is CoordinationAudience.CUSTOMER
                else RequestEventAudience.STAFF_ONLY
            ),
        )
        return result.event

    async def request_return(
        self, actor: Actor, request_id: UUID, command: ReturnRequestCreate
    ) -> TrackedRequestEvent:
        request, route_member = await self._authorised_request(actor, request_id)
        actor_position = self._access.route_position(actor.role)
        if not route_member or actor_position is None:
            raise ObjectNotFound()
        target = await self._returns.route_target(request.id, command.target_unit_id)
        current_position = CURRENT_ROUTE_POSITION.get(request.status)
        if (
            target is None
            or target.position > actor_position
            or current_position is None
            or target.position >= current_position
        ):
            raise InvalidAction(
                "Select your unit or an earlier unit on this request route."
            )
        event = await self._events.append(
            request_id=request.id,
            actor_id=actor.id,
            event_type="OWNERSHIP_RETURN_REQUESTED",
            message=f"Return to {target.name} requested: {command.reason}",
            prior_status=request.status,
            next_status=request.status,
            audience=RequestEventAudience.STAFF_ONLY,
            details={"targetUnitId": str(command.target_unit_id)},
        )
        return self._event_view(event, actor.display_name)

    async def _authorised_request(
        self, actor: Actor, request_id: UUID
    ) -> tuple[ServiceRequest, bool]:
        request = await self._requests.request(request_id)
        if (
            request is None
            or actor.role is UserRole.PLATFORM_ADMIN
            or has_self_request_conflict(actor, request)
        ):
            raise ObjectNotFound()
        route_member = await self._access.has_route_membership(actor, request_id)
        if (
            request.requester_id != actor.id
            and not route_member
            and not can_view_request(actor, request)
        ):
            raise ObjectNotFound()
        return request, route_member

    @staticmethod
    def _event_view(event: RequestEvent, actor_name: str) -> TrackedRequestEvent:
        return TrackedRequestEvent(
            id=event.id,
            type=event.type,
            message=event.message,
            actor_display_name=actor_name,
            prior_status=event.prior_status,
            next_status=event.next_status,
            created_at=event.created_at,
        )
