"""SQLAlchemy queries that construct public request read models."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from istari_service.models import (
    Deliverable,
    DeliverableStatus,
    Feedback,
    RequestStatus,
    ServiceRequest,
)
from istari_service.repositories.clarification_views import clarification_views
from istari_service.repositories.product_availability import has_available_product
from istari_service.repositories.projection_pagination import (
    decode_cursor,
    encode_cursor,
)
from istari_service.repositories.request_participants import active_contributor_views
from istari_service.request_event_audience import RequestEventAudience
from istari_service.request_event_models import RequestEvent
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
        version=request.version,
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
    event_limit: int = 50,
    event_cursor: str | None = None,
    include_staff_events: bool = False,
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
    event_statement = (
        select(RequestEvent)
        .options(selectinload(RequestEvent.actor))
        .where(RequestEvent.request_id == request_id)
    )
    if not include_staff_events:
        event_statement = event_statement.where(
            RequestEvent.audience == RequestEventAudience.CUSTOMER_AND_STAFF
        )
    if event_cursor is not None:
        changed_at, event_id = decode_cursor(
            event_cursor, message="The request-history filters are invalid."
        )
        event_statement = event_statement.where(
            or_(
                RequestEvent.created_at < changed_at,
                and_(
                    RequestEvent.created_at == changed_at,
                    RequestEvent.id < event_id,
                ),
            )
        )
    event_rows = list(
        await session.scalars(
            event_statement.order_by(
                RequestEvent.created_at.desc(), RequestEvent.id.desc()
            ).limit(event_limit + 1)
        )
    )
    has_more_events = len(event_rows) > event_limit
    event_page = event_rows[:event_limit]
    events = list(reversed(event_page))
    events_next_cursor = (
        encode_cursor(event_page[-1].created_at, event_page[-1].id)
        if has_more_events and event_page
        else None
    )
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
        product_available=await has_available_product(session, request_id),
        feedback_submitted=feedback is not None,
    )
    return RequestDetail(
        **summary.model_dump(),
        service_category=request.service_category,
        description=request.description,
        question_to_answer=request.question_to_answer,
        desired_outcome=request.desired_outcome,
        background_context=request.background_context,
        subject_area_or_location=request.subject_area_or_location,
        coverage_start=request.coverage_start,
        coverage_end=request.coverage_end,
        customer_urgency=request.customer_urgency,
        supported_activity_or_decision=request.supported_activity_or_decision,
        required_by_reason=request.required_by_reason,
        preferred_deliverable_type=request.preferred_deliverable_type,
        success_criteria=request.success_criteria,
        constraints_or_caveats=request.constraints_or_caveats,
        supporting_information=request.supporting_information,
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
        contributors=await active_contributor_views(session, request_id),
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
        events_next_cursor=events_next_cursor,
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
