"""Scoped SQLAlchemy adapter for explainable related-request matching."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import ColumnElement, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import Actor
from mist_service.errors import InvalidAction, StaleVersion
from mist_service.identity_context import active_actor_condition
from mist_service.models import (
    Deliverable,
    DeliverableStatus,
    RequestStatus,
    ServiceRequest,
    User,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTaskStatus,
)
from mist_service.models import WorkflowTask as StoredWorkflowTask
from mist_service.related_record_models import RequestLink, RequestLinkType
from mist_service.related_record_types import RelatedRecordSource
from mist_service.repositories.event_store import append_request_event
from mist_service.repositories.related_record_search import RelatedRecordSearch
from mist_service.repositories.route_access import route_membership_condition
from mist_service.repositories.work_scope import work_scope_conditions
from mist_service.schemas.related_records import (
    RelatedRecordCandidate,
    RelatedRecordCandidateList,
    RequestLinkCreate,
    RequestLinkView,
    RequestLinkWorkspace,
)


class SqlAlchemyRelatedRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def source(
        self,
        work_id: UUID,
        actor: Actor,
        *,
        lock: bool,
    ) -> RelatedRecordSource | None:
        query = (
            select(StoredWorkflowTask, ServiceRequest, WorkflowInstance, User)
            .join(ServiceRequest, ServiceRequest.id == StoredWorkflowTask.request_id)
            .join(
                WorkflowInstance,
                WorkflowInstance.id == StoredWorkflowTask.workflow_instance_id,
            )
            .join(User, User.id == StoredWorkflowTask.assignee_user_id)
            .where(
                StoredWorkflowTask.id == work_id,
                StoredWorkflowTask.status == WorkflowTaskStatus.CLAIMED,
                StoredWorkflowTask.assignee_user_id == actor.id,
                ServiceRequest.status == RequestStatus.TRIAGE_REVIEW,
                WorkflowInstance.status == WorkflowInstanceStatus.ACTIVE,
                WorkflowInstance.current_element_id == StoredWorkflowTask.element_id,
                WorkflowInstance.process_instance_key.is_not(None),
                active_actor_condition(actor),
                *work_scope_conditions(actor),
            )
        )
        if lock:
            query = query.with_for_update()
        row = (await self._session.execute(query)).one_or_none()
        if row is None:
            return None
        return RelatedRecordSource(row[1].id, row[1].version)

    async def search(
        self,
        source_id: UUID,
        actor: Actor,
        query: str | None,
        limit: int,
    ) -> RelatedRecordCandidateList:
        return await RelatedRecordSearch(self._session).search(
            source_id,
            actor,
            query=query,
            limit=limit,
        )

    async def links(self, source_id: UUID) -> list[RequestLinkView]:
        target = ServiceRequest
        released = _released_product_exists()
        rows = (
            await self._session.execute(
                select(RequestLink, target, released.label("product_available"))
                .join(target, target.id == RequestLink.target_request_id)
                .where(RequestLink.source_request_id == source_id)
                .order_by(RequestLink.created_at, RequestLink.id)
            )
        ).all()
        return [
            _link_view(link, request, available) for link, request, available in rows
        ]

    async def create(
        self,
        source: RelatedRecordSource,
        actor: Actor,
        command: RequestLinkCreate,
    ) -> RequestLinkWorkspace:
        request = await self._session.get(ServiceRequest, source.request_id)
        if request is None:
            raise InvalidAction()
        if request.version != command.expected_version:
            raise StaleVersion()
        target = await self._target(actor, command.target_request_id)
        if target is None or target.id == request.id:
            raise InvalidAction("Select another authorised request.")
        product_available = await self._session.scalar(
            select(_released_product_exists()).where(ServiceRequest.id == target.id)
        )
        if (
            command.link_type is RequestLinkType.EXISTING_OUTPUT
            and not product_available
        ):
            raise InvalidAction("The selected request has no released product.")
        link = RequestLink(
            source_request_id=request.id,
            target_request_id=target.id,
            link_type=command.link_type,
            reason=command.reason.strip(),
            created_by_user_id=actor.id,
            actor_display_name=actor.display_name,
        )
        self._session.add(link)
        request.version += 1
        try:
            await append_request_event(
                self._session,
                request_id=request.id,
                actor_id=actor.id,
                event_type="related_record_linked",
                message="Related-request decision recorded.",
                prior_status=request.status,
                next_status=request.status,
                details={
                    "linkType": command.link_type.value,
                    "targetReference": target.reference,
                },
            )
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise InvalidAction(
                "That related-record link is already recorded."
            ) from exc
        return RequestLinkWorkspace(
            source_version=request.version,
            items=await self.links(request.id),
        )

    async def _target(self, actor: Actor, target_id: UUID) -> ServiceRequest | None:
        membership = route_membership_condition(actor)
        if membership is None:
            return None
        return cast(
            ServiceRequest | None,
            await self._session.scalar(
                select(ServiceRequest).where(
                    ServiceRequest.id == target_id,
                    ServiceRequest.requester_id != actor.id,
                    membership,
                )
            ),
        )


def _released_product_exists() -> ColumnElement[bool]:
    return exists().where(
        Deliverable.request_id == ServiceRequest.id,
        Deliverable.status == DeliverableStatus.RELEASED,
        Deliverable.released_at.is_not(None),
    )


def _candidate(
    request: ServiceRequest, product_available: bool
) -> RelatedRecordCandidate:
    return RelatedRecordCandidate(
        id=request.id,
        reference=request.reference,
        title=request.title,
        status=request.status,
        required_by=request.required_by,
        product_available=product_available,
    )


def _link_view(
    link: RequestLink,
    target: ServiceRequest,
    product_available: bool,
) -> RequestLinkView:
    return RequestLinkView(
        id=link.id,
        target=_candidate(target, product_available),
        link_type=link.link_type,
        reason=link.reason,
        actor_display_name=link.actor_display_name,
        created_at=link.created_at,
    )
