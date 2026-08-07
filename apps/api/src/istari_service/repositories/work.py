"""SQLAlchemy work-queue and transition adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from istari_service.domain import Actor, WorkRecord
from istari_service.errors import InvalidAction
from istari_service.models import (
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTaskStatus,
)
from istari_service.models import (
    WorkflowTask as StoredWorkflowTask,
)
from istari_service.organisation_models import (
    OrganisationUnit,
    UserOrganisationMembership,
)
from istari_service.ownership import OWNER_BY_STATUS
from istari_service.repositories.auth import actor_from_user
from istari_service.repositories.event_store import append_request_event
from istari_service.repositories.organisation import SqlAlchemyOrganisationRepository
from istari_service.repositories.request_views import build_request_detail
from istari_service.repositories.task_projection import next_task_projection
from istari_service.repositories.work_actions import (
    apply_work_effect,
    event_message,
    validate_work_effect,
    work_event_details,
)
from istari_service.repositories.work_intents import (
    prepare_claim_intent,
    prepare_completion_intent,
)
from istari_service.repositories.work_scope import work_scope_conditions
from istari_service.repositories.work_views import build_work_bundle
from istari_service.schemas.organisation import OrganisationUnitView
from istari_service.schemas.requests import RequestDetail
from istari_service.schemas.work import CompletionPayload, WorkItem
from istari_service.services.work_service import WorkBundle
from istari_service.work_command_types import RoutingSelection
from istari_service.workflow.projection import (
    NEXT_TASK_RECONCILIATION_MESSAGE,
    status_after_action,
)
from istari_service.workflow.types import WorkflowAction, WorkflowTask


class SqlAlchemyWorkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_actor(self, actor: Actor) -> list[WorkBundle]:
        rows = (
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
                .where(
                    *work_scope_conditions(actor),
                )
                .order_by(StoredWorkflowTask.created_at, StoredWorkflowTask.id)
            )
        ).all()
        return [
            build_work_bundle(task, request, instance)
            for task, request, instance in rows
            if instance.process_instance_key is not None
        ]

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
        return build_work_bundle(*row)

    async def find_specialist(self, user_id: UUID) -> Actor | None:
        user = await self._session.get(User, user_id)
        if user is None or not user.is_active:
            return None
        return actor_from_user(user)

    async def list_active_specialists(self, delivery_team: str) -> list[Actor]:
        users = (
            await self._session.scalars(
                select(User)
                .join(
                    UserOrganisationMembership,
                    UserOrganisationMembership.user_id == User.id,
                )
                .join(
                    OrganisationUnit,
                    OrganisationUnit.id == UserOrganisationMembership.unit_id,
                )
                .where(
                    User.role == UserRole.DELIVERY_SPECIALIST,
                    User.scope == delivery_team,
                    User.is_active.is_(True),
                    OrganisationUnit.name == delivery_team,
                    OrganisationUnit.is_configured.is_(True),
                )
                .order_by(User.display_name, User.id)
            )
        ).all()
        return [actor_from_user(user) for user in users]

    async def routing_options(
        self,
        work: WorkRecord,
    ) -> list[OrganisationUnitView]:
        return await SqlAlchemyOrganisationRepository(self._session).routing_options(
            work.request.id,
            work.request.status,
        )

    async def validate_completion(
        self,
        work: WorkRecord,
        actor: Actor,
        payload: CompletionPayload,
    ) -> None:
        request = await self._session.get(ServiceRequest, work.request.id)
        if request is None:
            raise InvalidAction()
        await validate_work_effect(self._session, request, actor, payload)

    async def prepare_claim(self, work: WorkRecord, actor: Actor) -> UUID:
        return await prepare_claim_intent(self._session, work, actor)

    async def prepare_completion(
        self,
        work: WorkRecord,
        actor: Actor,
        payload: CompletionPayload,
    ) -> UUID:
        return await prepare_completion_intent(self._session, work, actor, payload)

    async def commit_intent(self) -> None:
        await self._session.commit()

    def expire_state(self) -> None:
        self._session.expire_all()

    async def request_detail(self, request_id: UUID) -> RequestDetail:
        return await build_request_detail(
            self._session,
            request_id,
            reveal_unreleased_deliverable=True,
        )

    async def finalise_claim(
        self,
        work: WorkRecord,
        actor: Actor,
    ) -> WorkItem | None:
        result = await self._session.execute(
            update(StoredWorkflowTask)
            .where(
                StoredWorkflowTask.id == work.id,
                StoredWorkflowTask.status == WorkflowTaskStatus.CLAIM_PENDING,
                StoredWorkflowTask.assignee_user_id == actor.id,
            )
            .values(
                status=WorkflowTaskStatus.CLAIMED,
                claimed_at=datetime.now(UTC),
            )
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            return None
        await self._session.flush()
        request = await self._session.get(ServiceRequest, work.request.id)
        if request is None:
            return None
        request.workflow_error = None
        await append_request_event(
            self._session,
            request_id=request.id,
            actor_id=actor.id,
            event_type="workflow_claimed",
            message="Work item claimed.",
            prior_status=request.status,
            next_status=request.status,
            details={"taskKey": work.engine_task_key},
        )
        await self._session.flush()
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
            or task.assignee_user_id != actor.id
            or request.status != work.request.status
            or request.version != work.request.version
        ):
            raise InvalidAction()
        await validate_work_effect(self._session, request, actor, payload)
        prior_status = request.status
        action = WorkflowAction(payload.action)
        next_status = status_after_action(prior_status, action)
        await apply_work_effect(self._session, request, actor, payload, routing)
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
            details=work_event_details(action, routing),
        )
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
        )
