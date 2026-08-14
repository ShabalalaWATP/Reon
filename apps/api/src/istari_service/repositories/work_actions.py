"""Persistence side effects for validated human completion commands."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.errors import InvalidAction
from istari_service.models import (
    Deliverable,
    DeliverableStatus,
    ProductMode,
    RequestStatus,
    ServiceRequest,
    UserRole,
    WorkflowTask,
    WorkflowTaskStatus,
)
from istari_service.product_models import ProductPackage
from istari_service.qc_membership import is_live_qc_manager
from istari_service.repositories.clarifications import (
    apply_clarification_effect,
    validate_clarification_effect,
    withdraw_open_clarification,
)
from istari_service.repositories.organisation import (
    apply_routing_selection,
    clear_route_from,
)
from istari_service.repositories.product_workflow import (
    validate_product_workflow_effect,
)
from istari_service.repositories.request_participants import (
    replace_request_participants,
)
from istari_service.schemas.work import (
    AllocateRequest,
    ApproveWork,
    AssignSpecialist,
    ChangesRequired,
    CompletionPayload,
    ProgressRequest,
    ProvideClarification,
    ReleaseDeliverable,
    RequestClarification,
    ReturnForReallocation,
    ReturnToCoordination,
    ReturnToTriage,
    SubmitDeliverable,
)
from istari_service.work_command_types import RoutingSelection
from istari_service.workflow.types import WorkflowAction


async def latest_deliverable(
    session: AsyncSession,
    request_id: UUID,
) -> Deliverable | None:
    return cast(
        Deliverable | None,
        await session.scalar(
            select(Deliverable)
            .where(Deliverable.request_id == request_id)
            .order_by(Deliverable.version.desc())
            .limit(1)
        ),
    )


async def validate_work_effect(
    session: AsyncSession,
    request: ServiceRequest,
    actor: Actor,
    payload: CompletionPayload,
    *,
    managed_products_enabled: bool = False,
) -> bool:
    del managed_products_enabled
    if (
        actor.role is UserRole.QUALITY_RELEASE
        and request.status
        in {RequestStatus.QUALITY_REVIEW, RequestStatus.READY_FOR_RELEASE}
        and not await is_live_qc_manager(session, actor.id, at=datetime.now(UTC))
    ):
        raise InvalidAction("A current Combined QC Team membership is required.")
    managed_product = False
    if request.product_mode is ProductMode.MANAGED:
        managed_product = await validate_product_workflow_effect(
            session, request, actor.id, payload
        )
    if (
        isinstance(payload, (SubmitDeliverable, ReleaseDeliverable))
        and payload.managed_product
        and not managed_product
    ):
        raise InvalidAction("An immutable managed product package is required.")
    if isinstance(payload, (RequestClarification, ProvideClarification)):
        await validate_clarification_effect(session, request, actor, payload)
    if isinstance(payload, AssignSpecialist) and request.requester_id in {
        payload.specialist_id,
        *payload.contributor_ids,
    }:
        raise InvalidAction("A Customer cannot be assigned to their own request.")
    if not managed_product and isinstance(
        payload, (ChangesRequired, ApproveWork, ReleaseDeliverable)
    ):
        deliverable = await latest_deliverable(session, request.id)
        if deliverable is None:
            raise InvalidAction("A deliverable is required for this action.")
        if (
            isinstance(payload, ApproveWork)
            and request.status == RequestStatus.QUALITY_REVIEW
            and deliverable.author_user_id == actor.id
        ):
            raise InvalidAction("A deliverable author cannot approve their own work.")
        if (
            isinstance(payload, ReleaseDeliverable)
            and deliverable.status != DeliverableStatus.APPROVED
        ):
            raise InvalidAction("Only the approved deliverable can be released.")
    if (
        isinstance(payload, ApproveWork)
        and request.status is RequestStatus.QUALITY_REVIEW
    ):
        await _require_independent_quality_reviewer(session, request.id, actor.id)
    elif isinstance(payload, ReleaseDeliverable):
        await _require_independent_release_manager(session, request.id, actor.id)
    return managed_product


async def _require_independent_quality_reviewer(
    session: AsyncSession, request_id: UUID, actor_id: UUID
) -> None:
    excluded = await _product_decision_participants(session, request_id)
    manager_reviewer = await _latest_completed_task_actor(
        session, request_id, "lead_review"
    )
    if actor_id in excluded or actor_id == manager_reviewer:
        raise InvalidAction(
            "The product author or Manager reviewer cannot perform QC review."
        )


async def _require_independent_release_manager(
    session: AsyncSession, request_id: UUID, actor_id: UUID
) -> None:
    excluded = await _product_decision_participants(session, request_id)
    manager_reviewer = await _latest_completed_task_actor(
        session, request_id, "lead_review"
    )
    quality_reviewer = await _latest_completed_task_actor(
        session, request_id, "quality_review"
    )
    if actor_id in excluded or actor_id in {manager_reviewer, quality_reviewer}:
        raise InvalidAction(
            "The product author, Manager reviewer and QC reviewer cannot disseminate "
            "the same product."
        )


async def _product_decision_participants(
    session: AsyncSession, request_id: UUID
) -> frozenset[UUID]:
    package = await session.scalar(
        select(ProductPackage)
        .where(ProductPackage.request_id == request_id)
        .order_by(ProductPackage.package_version.desc())
        .limit(1)
    )
    deliverable = await latest_deliverable(session, request_id)
    values = {
        package.author_user_id if package else None,
        package.manager_approved_by_user_id if package else None,
        deliverable.author_user_id if deliverable else None,
        deliverable.approved_by_user_id if deliverable else None,
    }
    return frozenset(value for value in values if value is not None)


async def _latest_completed_task_actor(
    session: AsyncSession, request_id: UUID, element_id: str
) -> UUID | None:
    return await session.scalar(
        select(WorkflowTask.assignee_user_id)
        .where(
            WorkflowTask.request_id == request_id,
            WorkflowTask.element_id == element_id,
            WorkflowTask.status == WorkflowTaskStatus.COMPLETED,
            WorkflowTask.assignee_user_id.is_not(None),
        )
        .order_by(WorkflowTask.completed_at.desc(), WorkflowTask.id.desc())
        .limit(1)
    )


async def apply_work_effect(
    session: AsyncSession,
    request: ServiceRequest,
    actor: Actor,
    payload: CompletionPayload,
    routing: RoutingSelection | None = None,
    *,
    managed_product: bool = False,
) -> None:
    now = datetime.now(UTC)
    await apply_routing_selection(session, request, routing)
    if isinstance(payload, (RequestClarification, ProvideClarification)):
        await apply_clarification_effect(session, request, actor, payload)
    elif payload.action == "withdraw":
        await withdraw_open_clarification(
            session,
            request,
            actor,
            payload.reason,
        )
    if isinstance(payload, ReturnToTriage):
        await clear_route_from(session, request, 1)
    elif isinstance(payload, ReturnToCoordination):
        await clear_route_from(session, request, 2)
    elif isinstance(payload, ReturnForReallocation):
        await clear_route_from(session, request, 3)
    if isinstance(payload, ProgressRequest):
        request.priority = payload.priority
    elif isinstance(payload, AllocateRequest):
        request.required_capabilities = payload.required_capabilities
    elif isinstance(payload, AssignSpecialist):
        request.assigned_specialist_id = payload.specialist_id
        await replace_request_participants(
            session,
            request_id=request.id,
            lead_id=payload.specialist_id,
            contributor_ids=payload.contributor_ids,
            actor_id=actor.id,
            reason=payload.reason,
        )
    elif isinstance(payload, SubmitDeliverable) and not managed_product:
        latest_version = await session.scalar(
            select(func.max(Deliverable.version)).where(
                Deliverable.request_id == request.id
            )
        )
        session.add(
            Deliverable(
                request_id=request.id,
                version=(latest_version or 0) + 1,
                title=cast(str, payload.deliverable_title),
                text=cast(str, payload.deliverable_text),
                author_user_id=actor.id,
                status=DeliverableStatus.SUBMITTED,
            )
        )
    elif isinstance(payload, ChangesRequired) and not managed_product:
        deliverable = await latest_deliverable(session, request.id)
        if deliverable is None:
            raise InvalidAction()
        deliverable.status = DeliverableStatus.CHANGES_REQUIRED
    elif (
        not managed_product
        and isinstance(payload, ApproveWork)
        and request.status == RequestStatus.QUALITY_REVIEW
    ):
        deliverable = await latest_deliverable(session, request.id)
        if deliverable is None or deliverable.author_user_id == actor.id:
            raise InvalidAction()
        deliverable.status = DeliverableStatus.APPROVED
        deliverable.approved_by_user_id = actor.id
        deliverable.approved_at = now
    elif isinstance(payload, ReleaseDeliverable) and not managed_product:
        deliverable = await latest_deliverable(session, request.id)
        if deliverable is None or deliverable.status != DeliverableStatus.APPROVED:
            raise InvalidAction()
        deliverable.status = DeliverableStatus.RELEASED
        deliverable.released_by_user_id = actor.id
        deliverable.release_recipients = payload.recipients
        deliverable.released_at = now


def event_message(payload: CompletionPayload, current: RequestStatus) -> str:
    action = payload.action
    if hasattr(payload, "reason"):
        return f"{action.replace('_', ' ').capitalize()}: {payload.reason}"
    if hasattr(payload, "information"):
        return f"Information provided: {payload.information}"
    if hasattr(payload, "note") and payload.note:
        return f"{action.replace('_', ' ').capitalize()}: {payload.note}"
    labels = {
        "progress": "Intake review completed.",
        "send_to_allocation": "Request sent for allocation.",
        "resume": "Request resumed.",
        "allocate": "Delivery team allocated.",
        "assign": "Lead Analyst and Contributors assigned.",
        "submit": "Deliverable submitted for review.",
        "request_clarification": "Additional information requested from Customer.",
        "provide_clarification": "Customer supplied additional information.",
        "approve": (
            "Deliverable approved for release."
            if current == RequestStatus.QUALITY_REVIEW
            else "Deliverable sent for quality review."
        ),
        "release": "Deliverable released.",
    }
    return labels.get(action, "Request updated.")


def work_event_details(
    action: WorkflowAction,
    routing: RoutingSelection | None,
) -> dict[str, str | int]:
    details: dict[str, str | int] = {"action": action.value}
    if routing is not None:
        details.update(
            routeUnitId=str(routing.unit_id),
            routePosition=routing.position,
        )
    return details
