"""SQLAlchemy queries that construct public request read models."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from istari_service.models import (
    Deliverable,
    DeliverableStatus,
    Feedback,
    RequestEvent,
    RequestStatus,
    ServiceRequest,
)
from istari_service.repositories.clarification_views import clarification_views
from istari_service.schemas.requests import (
    DeliverableView,
    FeedbackView,
    RequestDetail,
    RequesterView,
    RequestEventView,
    RequestSummary,
    Sensitivity,
)


def summary_from_request(
    request: ServiceRequest,
    *,
    product_available: bool = False,
    feedback_submitted: bool = False,
) -> RequestSummary:
    return RequestSummary(
        id=request.id,
        reference=request.reference,
        title=request.title,
        status=request.status,
        current_owner=request.current_owner,
        required_by=request.required_by,
        created_at=request.created_at,
        updated_at=request.updated_at,
        needs_requester_input=request.status
        in {
            RequestStatus.INFORMATION_REQUIRED,
            RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
        },
        product_available=product_available,
        feedback_submitted=feedback_submitted,
    )


async def build_request_detail(
    session: AsyncSession,
    request_id: UUID,
    *,
    reveal_unreleased_deliverable: bool,
    include_clarifications: bool = False,
) -> RequestDetail:
    request = await session.scalar(
        select(ServiceRequest)
        .options(
            selectinload(ServiceRequest.requester),
            selectinload(ServiceRequest.assigned_specialist),
        )
        .where(ServiceRequest.id == request_id)
    )
    if request is None:
        raise LookupError("request no longer exists")
    events = (
        await session.scalars(
            select(RequestEvent)
            .options(selectinload(RequestEvent.actor))
            .where(RequestEvent.request_id == request_id)
            .order_by(RequestEvent.created_at, RequestEvent.id)
        )
    ).all()
    deliverable_query = (
        select(Deliverable)
        .where(Deliverable.request_id == request_id)
        .order_by(Deliverable.version.desc())
        .limit(1)
    )
    if not reveal_unreleased_deliverable:
        deliverable_query = deliverable_query.where(
            Deliverable.status == DeliverableStatus.RELEASED
        )
    deliverable = await session.scalar(deliverable_query)
    feedback = await session.scalar(
        select(Feedback).where(Feedback.request_id == request_id)
    )
    clarifications = (
        await clarification_views(session, request_id) if include_clarifications else []
    )
    specialist = request.assigned_specialist
    summary = summary_from_request(
        request,
        product_available=(
            deliverable is not None
            and deliverable.status is DeliverableStatus.RELEASED
            and deliverable.released_at is not None
        ),
        feedback_submitted=feedback is not None,
    )
    return RequestDetail(
        **summary.model_dump(),
        service_category=request.service_category,
        description=request.description,
        desired_outcome=request.desired_outcome,
        background_context=request.background_context,
        required_by_reason=request.required_by_reason,
        preferred_deliverable_type=request.preferred_deliverable_type,
        success_criteria=request.success_criteria,
        requesting_business_area=request.requesting_business_area,
        intended_recipients=request.intended_recipients,
        sensitivity=Sensitivity(request.sensitivity),
        handling_instructions=request.handling_instructions,
        requester=RequesterView(
            id=request.requester.id,
            display_name=request.requester.display_name,
        ),
        assigned_delivery_team=request.assigned_delivery_team,
        assigned_specialist=(
            RequesterView(id=specialist.id, display_name=specialist.display_name)
            if specialist
            else None
        ),
        events=[
            RequestEventView(
                id=event.id,
                type=event.type,
                message=event.message,
                actor_display_name=event.actor.display_name if event.actor else None,
                created_at=event.created_at,
            )
            for event in events
        ],
        deliverable=(
            DeliverableView(
                id=deliverable.id,
                title=deliverable.title,
                text=deliverable.text,
                released_at=deliverable.released_at,
            )
            if deliverable
            else None
        ),
        feedback=(
            FeedbackView(
                id=feedback.id,
                rating=feedback.rating,
                comments=feedback.comments,
                created_at=feedback.created_at,
            )
            if feedback
            else None
        ),
        clarifications=clarifications,
        workflow_error=request.workflow_error,
    )
