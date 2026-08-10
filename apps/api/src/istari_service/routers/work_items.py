"""Role-scoped work-list, claim and completion HTTP routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from istari_service.dependencies import (
    AppSettings,
    CurrentActor,
    DatabaseSession,
    MutationActor,
    SessionFactoryDependency,
    WorkflowDependency,
)
from istari_service.repositories.related_records import (
    SqlAlchemyRelatedRecordRepository,
)
from istari_service.repositories.work import SqlAlchemyWorkRepository
from istari_service.schemas.organisation import RoutingOptionsWorkspace
from istari_service.schemas.related_records import (
    RelatedRecordCandidateList,
    RequestLinkCreate,
    RequestLinkWorkspace,
)
from istari_service.schemas.requests import RequestDetail
from istari_service.schemas.work import (
    CompletionPayload,
    EligibleSpecialistList,
    WorkItem,
    WorkItemList,
)
from istari_service.services.related_record_service import RelatedRecordService
from istari_service.services.work_service import WorkService
from istari_service.workflow_command_dispatch import WorkflowCommandDispatcher

router = APIRouter(prefix="/work-items", tags=["work items"])


def _related_service(session: DatabaseSession) -> RelatedRecordService:
    return RelatedRecordService(SqlAlchemyRelatedRecordRepository(session))


def _service(
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
    settings: AppSettings,
) -> WorkService:
    return WorkService(
        SqlAlchemyWorkRepository(
            session, managed_products_enabled=settings.managed_products_enabled
        ),
        WorkflowCommandDispatcher(
            sessions,
            engine,
            managed_products_enabled=settings.managed_products_enabled,
        ),
    )


@router.get("", response_model=WorkItemList)
async def list_work_items(
    actor: CurrentActor,
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
    settings: AppSettings,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=500),
) -> WorkItemList:
    items, next_cursor = await _service(session, engine, sessions, settings).list_page(
        actor, limit=limit, cursor=cursor
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
    items = await _service(session, engine, sessions, settings).eligible_specialists(
        actor, work_id
    )
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
    return await _service(session, engine, sessions, settings).routing_options(
        actor, work_id
    )


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
    return await _related_service(session).search(actor, work_id, query, limit)


@router.get("/{work_id}/request-links", response_model=RequestLinkWorkspace)
async def list_request_links(
    work_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
) -> RequestLinkWorkspace:
    return await _related_service(session).links(actor, work_id)


@router.post("/{work_id}/request-links", response_model=RequestLinkWorkspace)
async def create_request_link(
    work_id: UUID,
    command: RequestLinkCreate,
    actor: MutationActor,
    session: DatabaseSession,
) -> RequestLinkWorkspace:
    return await _related_service(session).create(actor, work_id, command)


@router.post("/{work_id}/claim", response_model=WorkItem)
async def claim_work_item(
    work_id: UUID,
    actor: MutationActor,
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
    settings: AppSettings,
) -> WorkItem:
    return await _service(session, engine, sessions, settings).claim(actor, work_id)


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
    return await _service(session, engine, sessions, settings).complete(
        actor, work_id, command
    )
