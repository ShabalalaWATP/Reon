"""Human work-item use cases over repository and workflow ports."""

from __future__ import annotations

from uuid import UUID

from mist_service.authorisation import WorkOperation
from mist_service.domain import Actor, WorkRecord
from mist_service.errors import (
    AlreadyClaimed,
    InvalidAction,
    ObjectNotFound,
    WorkflowActionPending,
    WorkflowUnavailable,
)
from mist_service.models import UserRole, WorkflowTaskStatus
from mist_service.policies import (
    LOADED_UNDER_POOL_SCOPE,
    allowed_actions,
    decide_work_access,
    decide_work_completion,
)
from mist_service.schemas.organisation import RoutingOptionsWorkspace
from mist_service.schemas.requests import RequestDetail
from mist_service.schemas.work import (
    AssignSpecialist,
    CompletionPayload,
    EligibleSpecialist,
    WorkItem,
)
from mist_service.services.work_ports import CommandDispatcher, WorkRepository
from mist_service.work_types import WorkBundle
from mist_service.workflow.errors import (
    WorkflowConflict,
    WorkflowEngineUnavailable,
    WorkflowError,
    WorkflowTaskNotFound,
)
from mist_service.workflow.types import WorkflowAction

__all__ = ["CommandDispatcher", "WorkRepository", "WorkService"]


class WorkService:
    def __init__(
        self,
        repository: WorkRepository,
        dispatcher: CommandDispatcher,
    ) -> None:
        self._repository = repository
        self._dispatcher = dispatcher

    async def list_page(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
        unit_id: UUID | None = None,
        request_id: UUID | None = None,
    ) -> tuple[list[WorkItem], str | None]:
        bundles, next_cursor = await self._repository.page_for_actor(
            actor,
            limit=limit,
            cursor=cursor,
            unit_id=unit_id,
            request_id=request_id,
        )
        visible = [bundle for bundle in bundles if self._visible(actor, bundle)]
        return [self._with_actions(actor, bundle) for bundle in visible], next_cursor

    async def eligible_specialists(
        self,
        actor: Actor,
        work_id: UUID,
    ) -> list[EligibleSpecialist]:
        bundle = await self._repository.get(work_id, actor)
        if (
            bundle is None
            or not decide_work_access(
                actor,
                bundle.record,
                WorkOperation.LIST_ELIGIBLE_SPECIALISTS,
                pool_membership_verified=LOADED_UNDER_POOL_SCOPE,
            ).allowed
        ):
            raise ObjectNotFound()
        team_name = bundle.record.request.assigned_delivery_team
        team_id = bundle.record.request.assigned_delivery_team_id
        if team_name is None:
            raise ObjectNotFound()
        specialists = (
            await self._repository.list_active_specialists(team_name)
            if team_id is None
            else await self._repository.list_active_specialists(
                team_name,
                delivery_team_id=team_id,
            )
        )
        return [
            EligibleSpecialist(id=specialist.id, display_name=specialist.display_name)
            for specialist in specialists
            if specialist.id != bundle.record.request.requester_id
        ]

    async def routing_options(
        self,
        actor: Actor,
        work_id: UUID,
    ) -> RoutingOptionsWorkspace:
        bundle = await self._repository.get(work_id, actor)
        if (
            bundle is None
            or not decide_work_access(
                actor,
                bundle.record,
                WorkOperation.VIEW_ROUTING_OPTIONS,
                pool_membership_verified=LOADED_UNDER_POOL_SCOPE,
            ).allowed
        ):
            raise ObjectNotFound()
        return await self._repository.routing_options(bundle.record)

    async def claim(self, actor: Actor, work_id: UUID) -> WorkItem:
        bundle = await self._repository.get(work_id, actor)
        if (
            bundle is None
            or not decide_work_access(
                actor,
                bundle.record,
                WorkOperation.CLAIM,
                pool_membership_verified=LOADED_UNDER_POOL_SCOPE,
            ).allowed
        ):
            raise ObjectNotFound()
        if bundle.record.task_status in {
            WorkflowTaskStatus.CLAIM_PENDING,
            WorkflowTaskStatus.COMPLETION_PENDING,
            WorkflowTaskStatus.ERROR,
        }:
            raise WorkflowActionPending()
        if (
            bundle.record.task_status is WorkflowTaskStatus.CLAIMED
            and bundle.record.assignee_id == actor.id
        ):
            return self._with_actions(actor, bundle)
        if (
            bundle.record.task_status is not WorkflowTaskStatus.OPEN
            or bundle.record.assignee_id is not None
        ):
            raise ObjectNotFound()
        if bundle.record.engine_task_key is None:
            raise InvalidAction()
        outbox_id = await self._repository.prepare_claim(bundle.record, actor)
        await self._repository.commit_intent()
        try:
            processed = await self._dispatcher.dispatch(outbox_id)
        except WorkflowConflict as exc:
            raise AlreadyClaimed() from exc
        except WorkflowEngineUnavailable as exc:
            raise WorkflowUnavailable() from exc
        except WorkflowError as exc:
            raise InvalidAction() from exc
        if not processed:
            raise WorkflowUnavailable()
        self._repository.expire_state()
        claimed = await self._repository.get(work_id, actor)
        if (
            claimed is None
            or claimed.record.task_status is not WorkflowTaskStatus.CLAIMED
        ):
            raise AlreadyClaimed()
        return self._with_actions(actor, claimed)

    async def complete(
        self,
        actor: Actor,
        work_id: UUID,
        payload: CompletionPayload,
    ) -> RequestDetail:
        bundle = await self._repository.get(work_id, actor)
        if (
            bundle is None
            or not decide_work_access(
                actor,
                bundle.record,
                WorkOperation.COMPLETE,
                pool_membership_verified=LOADED_UNDER_POOL_SCOPE,
            ).allowed
        ):
            raise ObjectNotFound()
        if bundle.record.task_status in {
            WorkflowTaskStatus.CLAIM_PENDING,
            WorkflowTaskStatus.COMPLETION_PENDING,
            WorkflowTaskStatus.ERROR,
        }:
            raise WorkflowActionPending()
        if bundle.record.task_status is not WorkflowTaskStatus.CLAIMED:
            raise InvalidAction()
        action = WorkflowAction(payload.action)
        if not decide_work_completion(
            actor,
            bundle.record.request,
            action.value,
            bundle.record.assignee_id,
            pool_membership_verified=LOADED_UNDER_POOL_SCOPE,
        ).allowed:
            raise InvalidAction()
        await self._validate_assignment(bundle.record, payload)
        outbox_id = await self._repository.prepare_completion(
            bundle.record, actor, payload
        )
        await self._repository.commit_intent()
        try:
            processed = await self._dispatcher.dispatch(outbox_id)
        except WorkflowEngineUnavailable as exc:
            raise WorkflowUnavailable() from exc
        except (WorkflowConflict, WorkflowTaskNotFound) as exc:
            raise InvalidAction() from exc
        except WorkflowError as exc:
            raise InvalidAction() from exc
        if not processed:
            raise WorkflowUnavailable()
        self._repository.expire_state()
        return await self._repository.request_detail(bundle.record.request.id)

    async def _validate_assignment(
        self,
        work: WorkRecord,
        payload: CompletionPayload,
    ) -> None:
        if not isinstance(payload, AssignSpecialist):
            return
        team_id = work.request.assigned_delivery_team_id
        selected_ids = [payload.specialist_id, *payload.contributor_ids]
        if len(set(selected_ids)) != len(selected_ids):
            raise InvalidAction("The Lead Analyst cannot also be a Contributor.")
        specialists = [
            (
                await self._repository.find_specialist(user_id)
                if team_id is None
                else await self._repository.find_specialist(
                    user_id,
                    delivery_team_id=team_id,
                )
            )
            for user_id in selected_ids
        ]
        if any(
            specialist is None
            or specialist.role != UserRole.DELIVERY_SPECIALIST
            or (
                team_id is None
                and specialist.scope != work.request.assigned_delivery_team
            )
            for specialist in specialists
        ):
            raise InvalidAction(
                "Every selected Analyst must be an active member of this team."
            )

    @staticmethod
    def _visible(actor: Actor, bundle: WorkBundle) -> bool:
        return decide_work_access(
            actor,
            bundle.record,
            WorkOperation.VIEW,
            pool_membership_verified=LOADED_UNDER_POOL_SCOPE,
        ).allowed

    @staticmethod
    def _with_actions(actor: Actor, bundle: WorkBundle) -> WorkItem:
        assigned_to_actor = bundle.record.assignee_id == actor.id or (
            actor.role is UserRole.DELIVERY_SPECIALIST
            and actor.id in bundle.record.request.participant_ids
        )
        actions = (
            list(
                allowed_actions(
                    actor,
                    bundle.record.request,
                    pool_membership_verified=LOADED_UNDER_POOL_SCOPE,
                )
            )
            if bundle.record.task_status is WorkflowTaskStatus.CLAIMED
            and assigned_to_actor
            else []
        )
        return bundle.view.model_copy(
            update={
                "available_actions": actions,
                "assigned_to_current_user": assigned_to_actor,
                "assignment_role": (
                    "LEAD_ANALYST"
                    if actor.role is UserRole.DELIVERY_SPECIALIST
                    and bundle.record.request.assigned_specialist_id == actor.id
                    else "ANALYST"
                    if actor.role is UserRole.DELIVERY_SPECIALIST
                    and actor.id in bundle.record.request.participant_ids
                    else None
                ),
            }
        )
