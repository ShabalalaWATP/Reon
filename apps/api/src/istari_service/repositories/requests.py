"""SQLAlchemy adapter for requester-facing use cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor, RequestRecord
from istari_service.errors import ObjectNotFound
from istari_service.models import (
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
)
from istari_service.repositories.configuration_pins import (
    SqlAlchemyConfigurationPinRepository,
)
from istari_service.repositories.event_store import append_request_event
from istari_service.repositories.request_customer import RequestCustomerRepositoryMixin
from istari_service.repositories.request_route_initialisation import (
    initialise_request_route,
)
from istari_service.repositories.request_scope import scoped_request
from istari_service.repositories.request_views import (
    build_request_detail,
)
from istari_service.schemas.requests import (
    RequestCreate,
    RequestDetail,
)


def record_from_request(request: ServiceRequest) -> RequestRecord:
    return RequestRecord(
        id=request.id,
        requester_id=request.requester_id,
        status=request.status,
        assigned_delivery_team=request.assigned_delivery_team,
        assigned_delivery_team_id=getattr(request, "assigned_delivery_team_id", None),
        assigned_specialist_id=request.assigned_specialist_id,
        version=request.version,
    )


class SqlAlchemyRequestRepository(RequestCustomerRepositoryMixin):
    def __init__(
        self,
        session: AsyncSession,
        *,
        process_id: str,
        configuration_pins: SqlAlchemyConfigurationPinRepository | None = None,
    ) -> None:
        self._session = session
        self._process_id = process_id
        self._configuration_pins = configuration_pins

    async def create(
        self,
        actor: Actor,
        command: RequestCreate,
    ) -> RequestDetail:
        if self._configuration_pins is None:
            raise RuntimeError(
                "immutable workflow configuration is required for submission"
            )
        existing = await self._session.scalar(
            select(ServiceRequest).where(
                ServiceRequest.submission_key == command.submission_key
            )
        )
        if existing is not None:
            if existing.requester_id != actor.id:
                raise ObjectNotFound()
            return await self.get_detail(
                existing.id, reveal_unreleased_deliverable=False
            )
        request_id = uuid4()
        now = datetime.now(UTC)
        request = ServiceRequest(
            id=request_id,
            reference=f"SR-{now.year}-{request_id.hex[:8].upper()}",
            requester_id=actor.id,
            status=RequestStatus.ROUTING_PENDING,
            current_owner="JIOC Routing",
            **command.model_dump(),
        )
        self._session.add(request)
        await self._session.flush()
        pin = await self._configuration_pins.pin_request(request_id, now=now)
        pinned_process_id = pin.snapshot.get("processId")
        if not isinstance(pinned_process_id, str) or not pinned_process_id:
            pinned_process_id = self._process_id
        pinned_process_version = pin.snapshot.get("processVersion")
        if (
            not isinstance(pinned_process_version, int)
            or isinstance(pinned_process_version, bool)
            or pinned_process_version < 1
        ):
            pinned_process_version = None
        pinned_process_checksum = pin.snapshot.get("processChecksum")
        if (
            not isinstance(pinned_process_checksum, str)
            or len(pinned_process_checksum) != 64
        ):
            pinned_process_checksum = None
        self._session.add(
            WorkflowInstance(
                request_id=request_id,
                process_id=pinned_process_id,
                process_version=pinned_process_version,
                process_checksum=pinned_process_checksum,
                status=WorkflowInstanceStatus.START_PENDING,
            )
        )
        start_payload: dict[str, object] = {
            "requestId": str(request_id),
            "requesterId": str(actor.id),
            "processId": pinned_process_id,
        }
        if pinned_process_version is not None:
            start_payload["processVersion"] = pinned_process_version
        if pinned_process_checksum is not None:
            start_payload["processChecksum"] = pinned_process_checksum
        self._session.add(
            WorkflowOutbox(
                request_id=request_id,
                event_type="START_PROCESS",
                payload=start_payload,
                idempotency_key=f"start:{request_id}",
                status=OutboxStatus.PENDING,
                available_at=now,
            )
        )
        await self._session.flush()
        await initialise_request_route(
            self._session,
            request_id,
            root_id=pin.organisation_root_id,
        )
        await append_request_event(
            self._session,
            request_id=request_id,
            actor_id=actor.id,
            event_type="request_submitted",
            message="Request submitted.",
            prior_status=None,
            next_status=RequestStatus.ROUTING_PENDING,
        )
        await self._session.flush()
        return await build_request_detail(
            self._session,
            request_id,
            reveal_unreleased_deliverable=False,
        )

    async def get_record_for_actor(
        self,
        request_id: UUID,
        actor: Actor,
        *,
        lock: bool = False,
    ) -> RequestRecord | None:
        request = await scoped_request(
            self._session,
            request_id,
            actor,
            lock=lock,
        )
        return record_from_request(request) if request else None

    async def get_detail(
        self,
        request_id: UUID,
        *,
        reveal_unreleased_deliverable: bool,
        include_clarifications: bool = False,
        event_limit: int = 50,
        event_cursor: str | None = None,
    ) -> RequestDetail:
        return await build_request_detail(
            self._session,
            request_id,
            reveal_unreleased_deliverable=reveal_unreleased_deliverable,
            include_clarifications=include_clarifications,
            event_limit=event_limit,
            event_cursor=event_cursor,
        )
