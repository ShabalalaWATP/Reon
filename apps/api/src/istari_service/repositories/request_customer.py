"""Customer request feed, released legacy product and feedback persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor, ProductDownload
from istari_service.errors import FeedbackUnavailable
from istari_service.models import (
    Deliverable,
    DeliverableStatus,
    Feedback,
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
)
from istari_service.product_models import ProductPackage
from istari_service.repositories.event_store import append_request_event
from istari_service.repositories.product_availability import available_product_exists
from istari_service.repositories.projection_pagination import (
    decode_cursor,
    encode_cursor,
)
from istari_service.repositories.request_views import (
    summary_from_request,
)
from istari_service.schemas.requests import (
    FeedbackCreate,
    FeedbackView,
    RequestSummary,
)


class RequestCustomerRepositoryMixin:
    _session: AsyncSession

    async def list_for_requester(self, requester_id: UUID) -> list[RequestSummary]:
        items, _cursor = await self.page_for_requester(
            requester_id, limit=100, cursor=None
        )
        return items

    async def page_for_requester(
        self,
        requester_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[RequestSummary], str | None]:
        released_product = available_product_exists()
        submitted_feedback = exists(
            select(Feedback.id).where(Feedback.request_id == ServiceRequest.id)
        )
        statement = select(ServiceRequest, released_product, submitted_feedback).where(
            ServiceRequest.requester_id == requester_id
        )
        if cursor is not None:
            changed_at, request_id = decode_cursor(
                cursor, message="The request filters are invalid."
            )
            statement = statement.where(
                or_(
                    ServiceRequest.updated_at < changed_at,
                    and_(
                        ServiceRequest.updated_at == changed_at,
                        ServiceRequest.id < request_id,
                    ),
                )
            )
        rows = (
            await self._session.execute(
                statement.order_by(
                    ServiceRequest.updated_at.desc(),
                    ServiceRequest.id.desc(),
                ).limit(limit + 1)
            )
        ).all()
        page = rows[:limit]
        items = [
            summary_from_request(
                request,
                product_available=product_available,
                feedback_submitted=feedback_submitted,
            )
            for request, product_available, feedback_submitted in page
        ]
        next_cursor = None
        if len(rows) > limit and page:
            last = page[-1][0]
            next_cursor = encode_cursor(last.updated_at, last.id)
        return items, next_cursor

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
