"""Human work-item use cases over repository and workflow ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from istari_service.domain import Actor, WorkRecord
from istari_service.errors import (
    AlreadyClaimed,
    InvalidAction,
    ObjectNotFound,
    WorkflowActionPending,
    WorkflowUnavailable,
)
from istari_service.models import RequestStatus, UserRole, WorkflowTaskStatus
from istari_service.policies import allowed_actions, can_access_work, may_complete
from istari_service.schemas.organisation import RoutingOptionsWorkspace
from istari_service.schemas.requests import RequestDetail
from istari_service.schemas.work import (
    AssignSpecialist,
    CompletionPayload,
    EligibleSpecialist,
    WorkItem,
)
from istari_service.workflow.errors import (
    WorkflowConflict,
    WorkflowEngineUnavailable,
    WorkflowError,
    WorkflowTaskNotFound,
)
from istari_service.workflow.types import WorkflowAction


@dataclass(frozen=True, slots=True)
class WorkBundle:
    record: WorkRecord
    view: WorkItem


class WorkRepository(Protocol):
    async def list_for_actor(self, actor: Actor) -> list[WorkBundle]: ...

    async def page_for_actor(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[WorkBundle], str | None]: ...

    async def get(
        self,
        work_id: UUID,
        actor: Actor | None = None,
    ) -> WorkBundle | None: ...

    async def find_specialist(
        self,
        user_id: UUID,
        *,
        delivery_team_id: UUID | None = None,
    ) -> Actor | None: ...

    async def list_active_specialists(
        self,
        delivery_team: str,
        *,
        delivery_team_id: UUID | None = None,
    ) -> list[Actor]: ...

    async def routing_options(
        self,
        work: WorkRecord,
    ) -> RoutingOptionsWorkspace: ...

    async def prepare_claim(self, work: WorkRecord, actor: Actor) -> UUID: ...

    async def prepare_completion(
        self,
        work: WorkRecord,
        actor: Actor,
        payload: CompletionPayload,
    ) -> UUID: ...

    async def commit_intent(self) -> None: ...

    def expire_state(self) -> None: ...

    async def request_detail(self, request_id: UUID) -> RequestDetail: ...


class CommandDispatcher(Protocol):
    async def dispatch(self, outbox_id: UUID) -> bool: ...


class WorkService:
    def __init__(
        self,
        repository: WorkRepository,
        dispatcher: CommandDispatcher,
    ) -> None:
        self._repository = repository
        self._dispatcher = dispatcher

    async def list_items(self, actor: Actor) -> list[WorkItem]:
        bundles = await self._repository.list_for_actor(actor)
        visible = [bundle for bundle in bundles if self._visible(actor, bundle)]
        return [self._with_actions(actor, bundle) for bundle in visible]

    async def list_page(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[WorkItem], str | None]:
        bundles, next_cursor = await self._repository.page_for_actor(
            actor, limit=limit, cursor=cursor
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
            or actor.role != UserRole.DELIVERY_TEAM_LEAD
            or not self._visible(actor, bundle)
            or bundle.record.request.status != RequestStatus.DELIVERY_PLANNING
            or bundle.record.request.assigned_delivery_team is None
        ):
            raise ObjectNotFound()
        team_name = bundle.record.request.assigned_delivery_team
        team_id = bundle.record.request.assigned_delivery_team_id
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
        ]

    async def routing_options(
        self,
        actor: Actor,
        work_id: UUID,
    ) -> RoutingOptionsWorkspace:
        bundle = await self._repository.get(work_id, actor)
        if (
            bundle is None
            or not self._visible(actor, bundle)
            or bundle.record.request.status
            not in {
                RequestStatus.TRIAGE_REVIEW,
                RequestStatus.COORDINATION_REVIEW,
                RequestStatus.ALLOCATION_REVIEW,
            }
        ):
            raise ObjectNotFound()
        return await self._repository.routing_options(bundle.record)

    async def claim(self, actor: Actor, work_id: UUID) -> WorkItem:
        bundle = await self._repository.get(work_id, actor)
        if bundle is None or not self._visible(actor, bundle):
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
        if bundle is None or not self._visible(actor, bundle):
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
        if not may_complete(
            actor,
            bundle.record.request,
            action.value,
            bundle.record.assignee_id,
        ):
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
        specialist = (
            await self._repository.find_specialist(payload.specialist_id)
            if team_id is None
            else await self._repository.find_specialist(
                payload.specialist_id,
                delivery_team_id=team_id,
            )
        )
        if (
            specialist is None
            or specialist.role != UserRole.DELIVERY_SPECIALIST
            or (
                team_id is None
                and specialist.scope != work.request.assigned_delivery_team
            )
        ):
            raise InvalidAction(
                "The selected specialist is outside this delivery team."
            )

    @staticmethod
    def _visible(actor: Actor, bundle: WorkBundle) -> bool:
        if bundle.record.completed_at is not None or not can_access_work(
            actor, bundle.record.request
        ):
            return False
        if bundle.record.task_status is WorkflowTaskStatus.OPEN:
            return bundle.record.assignee_id is None
        return bundle.record.assignee_id == actor.id

    @staticmethod
    def _with_actions(actor: Actor, bundle: WorkBundle) -> WorkItem:
        actions = (
            list(allowed_actions(actor, bundle.record.request))
            if bundle.record.task_status is WorkflowTaskStatus.CLAIMED
            and bundle.record.assignee_id == actor.id
            else []
        )
        return bundle.view.model_copy(update={"available_actions": actions})
