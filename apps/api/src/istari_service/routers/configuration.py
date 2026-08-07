"""Thin HTTP boundary for bounded configuration administration."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from pydantic import AwareDatetime

from istari_service.configuration_events import ConfigurationEventPublisher
from istari_service.dependencies import (
    AppSettings,
    CurrentActor,
    DatabaseSession,
    ElevatedMutationActor,
)
from istari_service.repositories.configuration import (
    SqlAlchemyConfigurationRepository,
)
from istari_service.schemas.configuration import (
    ApprovedWorkflowDefinitionList,
    ConfigurationDraftCreate,
    ConfigurationDraftReplace,
    ConfigurationOrganisationSnapshot,
    ConfigurationPreview,
    ConfigurationReasonCommand,
    ConfigurationVersionCommand,
    ConfigurationVersionDetail,
    ConfigurationVersionList,
)
from istari_service.services.configuration_lifecycle_service import (
    ConfigurationLifecycleService,
)
from istari_service.services.configuration_query_service import (
    ConfigurationQueryService,
)

router = APIRouter(
    prefix="/admin/configuration",
    tags=["platform-configuration"],
)


def _query(
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationQueryService:
    return ConfigurationQueryService(
        SqlAlchemyConfigurationRepository(session), settings
    )


def _lifecycle(
    request: Request,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationLifecycleService:
    publisher = cast(
        ConfigurationEventPublisher | None,
        getattr(request.app.state, "configuration_event_publisher", None),
    )
    return ConfigurationLifecycleService(
        SqlAlchemyConfigurationRepository(session), settings, publisher
    )


@router.get("/versions", response_model=ConfigurationVersionList)
async def list_versions(
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationVersionList:
    return await _query(session, settings).list_versions(actor)


@router.post(
    "/versions",
    response_model=ConfigurationVersionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    payload: ConfigurationDraftCreate,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationVersionDetail:
    return await _lifecycle(request, session, settings).create(actor, payload)


@router.get("/versions/{version_id}", response_model=ConfigurationVersionDetail)
async def get_version(
    version_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationVersionDetail:
    return await _query(session, settings).get_version(actor, version_id)


@router.put("/versions/{version_id}", response_model=ConfigurationVersionDetail)
async def replace_version(
    version_id: UUID,
    payload: ConfigurationDraftReplace,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationVersionDetail:
    return await _lifecycle(request, session, settings).replace(
        actor, version_id, payload
    )


@router.post(
    "/versions/{version_id}/validate",
    response_model=ConfigurationVersionDetail,
)
async def validate_version(
    version_id: UUID,
    payload: ConfigurationVersionCommand,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationVersionDetail:
    return await _lifecycle(request, session, settings).validate(
        actor, version_id, payload
    )


@router.post("/versions/{version_id}/submit", response_model=ConfigurationVersionDetail)
async def submit_version(
    version_id: UUID,
    payload: ConfigurationReasonCommand,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationVersionDetail:
    return await _lifecycle(request, session, settings).submit(
        actor, version_id, payload
    )


@router.post(
    "/versions/{version_id}/approve", response_model=ConfigurationVersionDetail
)
async def approve_version(
    version_id: UUID,
    payload: ConfigurationReasonCommand,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationVersionDetail:
    return await _lifecycle(request, session, settings).approve(
        actor, version_id, payload
    )


@router.post("/versions/{version_id}/reject", response_model=ConfigurationVersionDetail)
async def reject_version(
    version_id: UUID,
    payload: ConfigurationReasonCommand,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationVersionDetail:
    return await _lifecycle(request, session, settings).reject(
        actor, version_id, payload
    )


@router.post(
    "/versions/{version_id}/activate", response_model=ConfigurationVersionDetail
)
async def activate_version(
    version_id: UUID,
    payload: ConfigurationReasonCommand,
    request: Request,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationVersionDetail:
    return await _lifecycle(request, session, settings).activate(
        actor, version_id, payload
    )


@router.get("/versions/{version_id}/preview", response_model=ConfigurationPreview)
async def preview_version(
    version_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationPreview:
    return await _query(session, settings).preview(actor, version_id)


@router.get(
    "/versions/{version_id}/organisation",
    response_model=ConfigurationOrganisationSnapshot,
)
async def organisation_snapshot(
    version_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
    at: Annotated[AwareDatetime | None, Query()] = None,
) -> ConfigurationOrganisationSnapshot:
    return await _query(session, settings).organisation(actor, version_id, at=at)


@router.get("/active", response_model=ConfigurationVersionDetail)
async def active_version(
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ConfigurationVersionDetail:
    return await _query(session, settings).active(actor)


@router.get("/workflow-definitions", response_model=ApprovedWorkflowDefinitionList)
async def workflow_definitions(
    actor: CurrentActor,
    session: DatabaseSession,
    settings: AppSettings,
) -> ApprovedWorkflowDefinitionList:
    return await _query(session, settings).workflow_definitions(actor)
