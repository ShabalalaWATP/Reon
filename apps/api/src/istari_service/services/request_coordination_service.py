"""Authorise and audit non-blocking request coordination."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.errors import InvalidAction, ObjectNotFound
from istari_service.models import (
    RequestStatus,
    ServiceRequest,
    UserRole,
)
from istari_service.policies import can_view_request
from istari_service.repositories.event_store import append_request_event
from istari_service.repositories.organisation import (
    ROUTE_POSITION_BY_ROLE,
)
from istari_service.repositories.request_coordination import (
    RequestCoordinationRepository,
)
from istari_service.request_event_audience import RequestEventAudience
from istari_service.request_event_models import RequestEvent
from istari_service.schemas.coordination import (
    CoordinationAudience,
    CoordinationMessageCreate,
    ReturnRequestCreate,
)
from istari_service.schemas.organisation import TrackedRequestEvent

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
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = RequestCoordinationRepository(session)

    async def post_message(
        self, actor: Actor, request_id: UUID, command: CoordinationMessageCreate
    ) -> TrackedRequestEvent:
        request, _route_member = await self._authorised_request(actor, request_id)
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
        event = await append_request_event(
            self._session,
            request_id=request.id,
            actor_id=actor.id,
            event_type="COORDINATION_MESSAGE",
            message=f"{label}: {command.body}",
            prior_status=request.status,
            next_status=request.status,
            audience=(
                RequestEventAudience.CUSTOMER_AND_STAFF
                if command.audience is CoordinationAudience.CUSTOMER
                else RequestEventAudience.STAFF_ONLY
            ),
            details={"audience": command.audience.value},
        )
        return self._event_view(event, actor.display_name)

    async def request_return(
        self, actor: Actor, request_id: UUID, command: ReturnRequestCreate
    ) -> TrackedRequestEvent:
        request, route_member = await self._authorised_request(actor, request_id)
        actor_position = ROUTE_POSITION_BY_ROLE.get(actor.role)
        if not route_member or actor_position is None:
            raise ObjectNotFound()
        target = await self._repository.route_target(request.id, command.target_unit_id)
        current_position = CURRENT_ROUTE_POSITION.get(request.status)
        if (
            target is None
            or target[1] > actor_position
            or current_position is None
            or target[1] >= current_position
        ):
            raise InvalidAction(
                "Select your unit or an earlier unit on this request route."
            )
        event = await append_request_event(
            self._session,
            request_id=request.id,
            actor_id=actor.id,
            event_type="OWNERSHIP_RETURN_REQUESTED",
            message=(f"Return to {target[0].name} requested: {command.reason}"),
            prior_status=request.status,
            next_status=request.status,
            audience=RequestEventAudience.STAFF_ONLY,
            details={"targetUnitId": str(command.target_unit_id)},
        )
        return self._event_view(event, actor.display_name)

    async def _authorised_request(
        self, actor: Actor, request_id: UUID
    ) -> tuple[ServiceRequest, bool]:
        request = await self._repository.request(request_id)
        if request is None or actor.role is UserRole.PLATFORM_ADMIN:
            raise ObjectNotFound()
        route_member = await self._repository.has_route_membership(actor, request_id)
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
