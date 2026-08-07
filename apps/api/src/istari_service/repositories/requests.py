"""SQLAlchemy adapter for requester-facing use cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor, ProductDownload, RequestRecord
from istari_service.errors import FeedbackUnavailable, ObjectNotFound
from istari_service.models import (
    Deliverable,
    DeliverableStatus,
    Feedback,
    OutboxStatus,
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
)
from istari_service.product_models import ProductPackage
from istari_service.repositories.configuration_pins import (
    SqlAlchemyConfigurationPinRepository,
)
from istari_service.repositories.event_store import append_request_event
from istari_service.repositories.product_availability import (
    available_product_exists,
)
from istari_service.repositories.request_route_initialisation import (
    initialise_request_route,
)
from istari_service.repositories.request_scope import scoped_request
from istari_service.repositories.request_views import (
    build_request_detail,
    summary_from_request,
)
from istari_service.schemas.requests import (
    FeedbackCreate,
    FeedbackView,
    RequestCreate,
    RequestDetail,
    RequestSummary,
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


class SqlAlchemyRequestRepository:
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

    async def list_for_requester(self, requester_id: UUID) -> list[RequestSummary]:
        released_product = available_product_exists()
        submitted_feedback = exists(
            select(Feedback.id).where(Feedback.request_id == ServiceRequest.id)
        )
        rows = (
            await self._session.execute(
                select(ServiceRequest, released_product, submitted_feedback)
                .where(ServiceRequest.requester_id == requester_id)
                .order_by(ServiceRequest.updated_at.desc())
            )
        ).all()
        return [
            summary_from_request(
                request,
                product_available=product_available,
                feedback_submitted=feedback_submitted,
            )
            for request, product_available, feedback_submitted in rows
        ]

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
    ) -> RequestDetail:
        return await build_request_detail(
            self._session,
            request_id,
            reveal_unreleased_deliverable=reveal_unreleased_deliverable,
            include_clarifications=include_clarifications,
        )

    async def feedback_exists(self, request_id: UUID) -> bool:
        return (
            await self._session.scalar(
                select(Feedback.id).where(Feedback.request_id == request_id)
            )
            is not None
        )

    async def get_released_product(
        self,
        request_id: UUID,
        requester_id: UUID,
    ) -> ProductDownload | None:
        request = (
            await self._session.execute(
                select(ServiceRequest.reference, ServiceRequest.status)
                .join(User, User.id == ServiceRequest.requester_id)
                .where(
                    ServiceRequest.id == request_id,
                    ServiceRequest.requester_id == requester_id,
                    User.is_active.is_(True),
                    User.role == UserRole.REQUESTER,
                )
                .with_for_update()
            )
        ).one_or_none()
        if request is None or request.status is not RequestStatus.COMPLETED:
            return None
        managed_package = await self._session.scalar(
            select(ProductPackage.id)
            .where(ProductPackage.request_id == request_id)
            .limit(1)
        )
        if managed_package is not None:
            return None
        deliverable = await self._session.scalar(
            select(Deliverable)
            .where(Deliverable.request_id == request_id)
            .order_by(Deliverable.version.desc())
            .limit(1)
            .with_for_update()
        )
        if (
            deliverable is None
            or deliverable.status is not DeliverableStatus.RELEASED
            or deliverable.released_at is None
        ):
            return None
        return ProductDownload(reference=request.reference, text=deliverable.text)

    async def add_feedback(
        self,
        request_id: UUID,
        actor: Actor,
        command: FeedbackCreate,
    ) -> FeedbackView:
        request = await self._session.scalar(
            select(ServiceRequest)
            .where(ServiceRequest.id == request_id)
            .with_for_update()
        )
        existing = await self._session.scalar(
            select(Feedback).where(Feedback.request_id == request_id)
        )
        if existing is not None:
            if (
                existing.requester_id == actor.id
                and existing.submission_key == command.submission_key
            ):
                return FeedbackView(
                    id=existing.id,
                    rating=existing.rating,
                    comments=existing.comments,
                    created_at=existing.created_at,
                )
            raise FeedbackUnavailable()
        if request is None or request.status != RequestStatus.COMPLETED:
            raise FeedbackUnavailable()
        feedback = Feedback(
            request_id=request_id,
            requester_id=actor.id,
            submission_key=command.submission_key,
            rating=command.rating,
            comments=command.comments,
        )
        self._session.add(feedback)
        await self._session.flush()
        await append_request_event(
            self._session,
            request_id=request_id,
            actor_id=actor.id,
            event_type="feedback_submitted",
            message="Feedback submitted.",
            prior_status=request.status,
            next_status=request.status,
        )
        return FeedbackView(
            id=feedback.id,
            rating=feedback.rating,
            comments=feedback.comments,
            created_at=feedback.created_at,
        )
