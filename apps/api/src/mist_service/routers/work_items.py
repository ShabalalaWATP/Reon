"""Role-scoped work-list, claim and completion HTTP routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from mist_service.dependencies import (
    AppSettings,
    CurrentActor,
    DatabaseSession,
    MutationActor,
    SessionFactoryDependency,
    WorkflowDependency,
)
from mist_service.schemas.organisation import RoutingOptionsWorkspace
from mist_service.schemas.related_records import (
    RelatedRecordCandidateList,
    RequestLinkCreate,
    RequestLinkWorkspace,
)
from mist_service.schemas.requests import RequestDetail
from mist_service.schemas.work import (
    CompletionPayload,
    EligibleSpecialistList,
    WorkItem,
    WorkItemList,
)
from mist_service.work_composition import (
    build_related_record_service,
    build_work_service,
)

router = APIRouter(prefix="/work-items", tags=["work items"])


@router.get("", response_model=WorkItemList)
async def list_work_items(
    actor: CurrentActor,
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
    settings: AppSettings,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=500),
    unit_id: Annotated[UUID | None, Query(alias="unitId")] = None,
    request_id: Annotated[UUID | None, Query(alias="requestId")] = None,
) -> WorkItemList:
    items, next_cursor = await build_work_service(
        session, engine, sessions, settings
    ).list_page(
        actor,
        limit=limit,
        cursor=cursor,
        unit_id=unit_id,
        request_id=request_id,
    )
    return WorkItemList(items=items, next_cursor=next_cursor)


@router.get(
    "/{work_id}/eligible-specialists",
    response_model=EligibleSpecialistList,
)
async def list_eligible_specialists(
    work_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
    settings: AppSettings,
) -> EligibleSpecialistList:
    items = await build_work_service(
        session, engine, sessions, settings
    ).eligible_specialists(actor, work_id)
    return EligibleSpecialistList(items=items)


@router.get("/{work_id}/routing-options", response_model=RoutingOptionsWorkspace)
async def list_routing_options(
    work_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
    settings: AppSettings,
) -> RoutingOptionsWorkspace:
    return await build_work_service(
        session, engine, sessions, settings
    ).routing_options(actor, work_id)


@router.get(
    "/{work_id}/related-records",
    response_model=RelatedRecordCandidateList,
)
async def search_related_records(
    work_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    query: str | None = Query(default=None, min_length=2, max_length=240),
    limit: int = Query(default=10, ge=1, le=20),
) -> RelatedRecordCandidateList:
    return await build_related_record_service(session).search(
        actor, work_id, query, limit
    )


@router.get("/{work_id}/request-links", response_model=RequestLinkWorkspace)
async def list_request_links(
    work_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
) -> RequestLinkWorkspace:
    return await build_related_record_service(session).links(actor, work_id)


@router.post("/{work_id}/request-links", response_model=RequestLinkWorkspace)
async def create_request_link(
    work_id: UUID,
    command: RequestLinkCreate,
    actor: MutationActor,
    session: DatabaseSession,
) -> RequestLinkWorkspace:
    return await build_related_record_service(session).create(actor, work_id, command)


@router.post("/{work_id}/claim", response_model=WorkItem)
async def claim_work_item(
    work_id: UUID,
    actor: MutationActor,
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
    settings: AppSettings,
) -> WorkItem:
    return await build_work_service(session, engine, sessions, settings).claim(
        actor, work_id
    )


@router.post("/{work_id}/complete", response_model=RequestDetail)
async def complete_work_item(
    work_id: UUID,
    command: CompletionPayload,
    actor: MutationActor,
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
    settings: AppSettings,
) -> RequestDetail:
    return await build_work_service(session, engine, sessions, settings).complete(
        actor, work_id, command
    )
