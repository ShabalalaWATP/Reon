"""SQLAlchemy work-queue and transition adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mist_service.domain import Actor, WorkRecord
from mist_service.errors import InvalidAction
from mist_service.models import (
    RequestStatus,
    ServiceRequest,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTaskStatus,
)
from mist_service.models import WorkflowTask as StoredWorkflowTask
from mist_service.organisation_models import RequestRouteSelection
from mist_service.ownership import OWNER_BY_STATUS
from mist_service.repositories.event_store import append_request_event
from mist_service.repositories.organisation import SqlAlchemyOrganisationRepository
from mist_service.repositories.product_workflow import product_workflow_details
from mist_service.repositories.projection_pagination import (
    decode_cursor,
    encode_cursor,
)
from mist_service.repositories.request_views import build_request_detail
from mist_service.repositories.route_access import ROUTE_POSITION_BY_ROLE
from mist_service.repositories.task_projection import next_task_projection
from mist_service.repositories.work_actions import (
    apply_work_effect,
    event_message,
    validate_work_effect,
    work_event_details,
)
from mist_service.repositories.work_claim_projection import project_claim
from mist_service.repositories.work_event_recording import append_routing_note
from mist_service.repositories.work_intent_repository import WorkIntentRepositoryMixin
from mist_service.repositories.work_scope import work_scope_conditions
from mist_service.repositories.work_staffing import WorkStaffingRepositoryMixin
from mist_service.repositories.work_views import build_work_bundle
from mist_service.schemas.organisation import RoutingOptionsWorkspace
from mist_service.schemas.requests import RequestDetail
from mist_service.schemas.work import CompletionPayload, WorkItem
from mist_service.work_command_types import RoutingSelection
from mist_service.work_types import WorkBundle
from mist_service.workflow.projection import (
    NEXT_TASK_RECONCILIATION_MESSAGE,
    status_after_action,
)
from mist_service.workflow.types import WorkflowAction, WorkflowTask
from mist_service.workflow_event_visibility import work_event_audience


class SqlAlchemyWorkRepository(WorkIntentRepositoryMixin, WorkStaffingRepositoryMixin):
    def __init__(
        self, session: AsyncSession, *, managed_products_enabled: bool = False
    ) -> None:
        self._session = session
        self._managed_products_enabled = managed_products_enabled

    async def list_for_actor(self, actor: Actor) -> list[WorkBundle]:
        items, _cursor = await self.page_for_actor(actor, limit=100, cursor=None)
        return items

    async def page_for_actor(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
        unit_id: UUID | None = None,
        request_id: UUID | None = None,
    ) -> tuple[list[WorkBundle], str | None]:
        statement = (
            select(StoredWorkflowTask, ServiceRequest, WorkflowInstance)
            .options(selectinload(StoredWorkflowTask.assignee))
            .join(
                ServiceRequest,
                ServiceRequest.id == StoredWorkflowTask.request_id,
            )
            .join(
                WorkflowInstance,
                WorkflowInstance.id == StoredWorkflowTask.workflow_instance_id,
            )
            .where(*work_scope_conditions(actor))
        )
        if unit_id is not None:
            position = ROUTE_POSITION_BY_ROLE.get(actor.role)
            statement = statement.where(
                ServiceRequest.id.is_(None)
                if position is None
                else select(RequestRouteSelection.id)
                .where(
                    RequestRouteSelection.request_id == ServiceRequest.id,
                    RequestRouteSelection.position == position,
                    RequestRouteSelection.unit_id == unit_id,
                )
                .exists()
            )
        if request_id is not None:
            statement = statement.where(StoredWorkflowTask.request_id == request_id)
        if cursor is not None:
            changed_at, work_id = decode_cursor(
                cursor, message="The work-item filters are invalid."
            )
            if self._session.get_bind().dialect.name == "sqlite":
                # SQLite's CURRENT_TIMESTAMP omits fractional seconds while a bound
                # datetime includes them, so raw text ordering can repeat the cursor.
                changed_column = func.julianday(StoredWorkflowTask.updated_at)
                changed_value = func.julianday(changed_at)
                cursor_filter = or_(
                    changed_column < changed_value,
                    and_(
                        changed_column == changed_value, StoredWorkflowTask.id < work_id
                    ),
                )
            else:
                cursor_filter = or_(
                    StoredWorkflowTask.updated_at < changed_at,
                    and_(
                        StoredWorkflowTask.updated_at == changed_at,
                        StoredWorkflowTask.id < work_id,
                    ),
                )
            statement = statement.where(cursor_filter)
        rows = (
            await self._session.execute(
                statement.order_by(
                    StoredWorkflowTask.updated_at.desc(),
                    StoredWorkflowTask.id.desc(),
                ).limit(limit + 1)
            )
        ).all()
        page = rows[:limit]
        items = [
            build_work_bundle(
                task,
                request,
                instance,
                participant_ids=(
                    frozenset({actor.id})
                    if actor.role is UserRole.DELIVERY_SPECIALIST
                    else frozenset()
                ),
            )
            for task, request, instance in page
            if instance.process_instance_key is not None
        ]
        next_cursor = None
        if len(rows) > limit and page:
            last = page[-1][0]
            next_cursor = encode_cursor(last.updated_at, last.id)
        return items, next_cursor

    async def get(
        self,
        work_id: UUID,
        actor: Actor | None = None,
    ) -> WorkBundle | None:
        scoped = work_scope_conditions(actor) if actor is not None else ()
        row = (
            await self._session.execute(
                select(StoredWorkflowTask, ServiceRequest, WorkflowInstance)
                .options(selectinload(StoredWorkflowTask.assignee))
                .join(
                    ServiceRequest,
                    ServiceRequest.id == StoredWorkflowTask.request_id,
                )
                .join(
                    WorkflowInstance,
                    WorkflowInstance.id == StoredWorkflowTask.workflow_instance_id,
                )
                .where(StoredWorkflowTask.id == work_id, *scoped)
            )
        ).one_or_none()
        if row is None or row[2].process_instance_key is None:
            return None
        return build_work_bundle(
            *row,
            participant_ids=(
                frozenset({actor.id})
                if actor is not None and actor.role is UserRole.DELIVERY_SPECIALIST
                else frozenset()
            ),
        )

    async def routing_options(
        self,
        work: WorkRecord,
    ) -> RoutingOptionsWorkspace:
        return await SqlAlchemyOrganisationRepository(self._session).routing_workspace(
            work.request.id,
            work.request.status,
        )

    async def request_detail(self, request_id: UUID) -> RequestDetail:
        return await build_request_detail(
            self._session,
            request_id,
            reveal_unreleased_deliverable=True,
            include_staff_events=True,
        )

    async def finalise_claim(
        self,
        work: WorkRecord,
        actor: Actor,
    ) -> WorkItem | None:
        if not await project_claim(self._session, work, actor):
            return None
        bundle = await self.get(work.id)
        return bundle.view if bundle else None

    async def apply_completion(
        self,
        work: WorkRecord,
        actor: Actor,
        payload: CompletionPayload,
        *,
        next_task: WorkflowTask | None,
        reconciliation_needed: bool,
        routing: RoutingSelection | None = None,
    ) -> RequestDetail:
        task = await self._session.scalar(
            select(StoredWorkflowTask)
            .where(StoredWorkflowTask.id == work.id)
            .with_for_update()
        )
        request = await self._session.scalar(
            select(ServiceRequest)
            .where(ServiceRequest.id == work.request.id)
            .with_for_update()
        )
        instance = await self._session.scalar(
            select(WorkflowInstance)
            .where(WorkflowInstance.request_id == work.request.id)
            .with_for_update()
        )
        if (
            task is None
            or request is None
            or instance is None
            or task.status != WorkflowTaskStatus.COMPLETION_PENDING
            or (
                task.assignee_user_id != actor.id
                and actor.id not in work.request.participant_ids
            )
            or request.status != work.request.status
            or request.version != work.request.version
        ):
            raise InvalidAction()
        managed_product = await validate_work_effect(
            self._session,
            request,
            actor,
            payload,
            managed_products_enabled=self._managed_products_enabled,
        )
        prior_status = request.status
        action = WorkflowAction(payload.action)
        next_status = status_after_action(prior_status, action)
        event_details = work_event_details(action, routing)
        if self._managed_products_enabled:
            event_details.update(
                await product_workflow_details(self._session, request.id, payload)
            )
        await apply_work_effect(
            self._session,
            request,
            actor,
            payload,
            routing,
            managed_product=managed_product,
        )
        now = datetime.now(UTC)
        task.status = WorkflowTaskStatus.COMPLETED
        task.completed_at = now
        request.status = next_status
        request.current_owner = (
            "Awaiting team staffing"
            if next_status is RequestStatus.DELIVERY_PLANNING
            and request.awaiting_team_staffing
            else OWNER_BY_STATUS[next_status]
        )
        request.version += 1
        request.workflow_error = (
            NEXT_TASK_RECONCILIATION_MESSAGE if reconciliation_needed else None
        )
        instance.current_element_id = next_task.element_id if next_task else None
        instance.last_reconciled_at = now if next_task else instance.last_reconciled_at
        if next_status in {
            RequestStatus.COMPLETED,
            RequestStatus.CLOSED_NOT_PROGRESSED,
            RequestStatus.CANCELLED,
        }:
            instance.status = WorkflowInstanceStatus.COMPLETED
            instance.completed_at = now
        elif next_task is not None:
            self._session.add(next_task_projection(request, instance, next_task))
        await append_request_event(
            self._session,
            request_id=request.id,
            actor_id=actor.id,
            event_type=f"workflow_{action.value}",
            message=event_message(payload, prior_status),
            prior_status=prior_status,
            next_status=next_status,
            audience=work_event_audience(action),
            details=event_details,
        )
        await append_routing_note(self._session, request, actor, payload, event_details)
        await self._session.flush()
        return await build_request_detail(
            self._session,
            request.id,
            reveal_unreleased_deliverable=True,
            include_clarifications=actor.role
            in {
                UserRole.DELIVERY_SPECIALIST,
                UserRole.DELIVERY_TEAM_LEAD,
                UserRole.REQUESTER,
            },
            include_staff_events=actor.role is not UserRole.REQUESTER,
        )
