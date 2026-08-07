"""Role-scoped work-list, claim and completion HTTP routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from istari_service.dependencies import (
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
from istari_service.schemas.organisation import OrganisationUnitList
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
) -> WorkService:
    return WorkService(
        SqlAlchemyWorkRepository(session),
        WorkflowCommandDispatcher(sessions, engine),
    )


@router.get("", response_model=WorkItemList)
async def list_work_items(
    actor: CurrentActor,
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
) -> WorkItemList:
    items = await _service(session, engine, sessions).list_items(actor)
    return WorkItemList(items=items)


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
) -> EligibleSpecialistList:
    items = await _service(session, engine, sessions).eligible_specialists(
        actor, work_id
    )
    return EligibleSpecialistList(items=items)


@router.get("/{work_id}/routing-options", response_model=OrganisationUnitList)
async def list_routing_options(
    work_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
) -> OrganisationUnitList:
    items = await _service(session, engine, sessions).routing_options(actor, work_id)
    return OrganisationUnitList(items=items)


@router.get(
    "/{work_id}/related-records",
    response_model=RelatedRecordCandidateList,
)
async def search_related_records(
    work_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    query: str = Query(min_length=2, max_length=120),
    limit: int = Query(default=20, ge=1, le=20),
) -> RelatedRecordCandidateList:
    items = await _related_service(session).search(actor, work_id, query, limit)
    return RelatedRecordCandidateList(items=items)


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
) -> WorkItem:
    return await _service(session, engine, sessions).claim(actor, work_id)


@router.post("/{work_id}/complete", response_model=RequestDetail)
async def complete_work_item(
    work_id: UUID,
    command: CompletionPayload,
    actor: MutationActor,
    session: DatabaseSession,
    engine: WorkflowDependency,
    sessions: SessionFactoryDependency,
) -> RequestDetail:
    return await _service(session, engine, sessions).complete(actor, work_id, command)
