"""Thin HTTP boundary for bounded configuration administration."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status
from pydantic import AwareDatetime

from istari_service.configuration_composition import (
    ConfigurationLifecycleDependency,
    ConfigurationQueryDependency,
)
from istari_service.dependencies import (
    CurrentActor,
    ElevatedMutationActor,
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

router = APIRouter(
    prefix="/admin/configuration",
    tags=["platform-configuration"],
)


@router.get("/versions", response_model=ConfigurationVersionList)
async def list_versions(
    actor: CurrentActor,
    service: ConfigurationQueryDependency,
) -> ConfigurationVersionList:
    return await service.list_versions(actor)


@router.post(
    "/versions",
    response_model=ConfigurationVersionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    payload: ConfigurationDraftCreate,
    actor: ElevatedMutationActor,
    service: ConfigurationLifecycleDependency,
) -> ConfigurationVersionDetail:
    return await service.create(actor, payload)


@router.get("/versions/{version_id}", response_model=ConfigurationVersionDetail)
async def get_version(
    version_id: UUID,
    actor: CurrentActor,
    service: ConfigurationQueryDependency,
) -> ConfigurationVersionDetail:
    return await service.get_version(actor, version_id)


@router.put("/versions/{version_id}", response_model=ConfigurationVersionDetail)
async def replace_version(
    version_id: UUID,
    payload: ConfigurationDraftReplace,
    actor: ElevatedMutationActor,
    service: ConfigurationLifecycleDependency,
) -> ConfigurationVersionDetail:
    return await service.replace(actor, version_id, payload)


@router.post(
    "/versions/{version_id}/validate",
    response_model=ConfigurationVersionDetail,
)
async def validate_version(
    version_id: UUID,
    payload: ConfigurationVersionCommand,
    actor: ElevatedMutationActor,
    service: ConfigurationLifecycleDependency,
) -> ConfigurationVersionDetail:
    return await service.validate(actor, version_id, payload)


@router.post("/versions/{version_id}/submit", response_model=ConfigurationVersionDetail)
async def submit_version(
    version_id: UUID,
    payload: ConfigurationReasonCommand,
    actor: ElevatedMutationActor,
    service: ConfigurationLifecycleDependency,
) -> ConfigurationVersionDetail:
    return await service.submit(actor, version_id, payload)


@router.post(
    "/versions/{version_id}/approve", response_model=ConfigurationVersionDetail
)
async def approve_version(
    version_id: UUID,
    payload: ConfigurationReasonCommand,
    actor: ElevatedMutationActor,
    service: ConfigurationLifecycleDependency,
) -> ConfigurationVersionDetail:
    return await service.approve(actor, version_id, payload)


@router.post("/versions/{version_id}/reject", response_model=ConfigurationVersionDetail)
async def reject_version(
    version_id: UUID,
    payload: ConfigurationReasonCommand,
    actor: ElevatedMutationActor,
    service: ConfigurationLifecycleDependency,
) -> ConfigurationVersionDetail:
    return await service.reject(actor, version_id, payload)


@router.post(
    "/versions/{version_id}/activate", response_model=ConfigurationVersionDetail
)
async def activate_version(
    version_id: UUID,
    payload: ConfigurationReasonCommand,
    actor: ElevatedMutationActor,
    service: ConfigurationLifecycleDependency,
) -> ConfigurationVersionDetail:
    return await service.activate(actor, version_id, payload)


@router.get("/versions/{version_id}/preview", response_model=ConfigurationPreview)
async def preview_version(
    version_id: UUID,
    actor: CurrentActor,
    service: ConfigurationQueryDependency,
) -> ConfigurationPreview:
    return await service.preview(actor, version_id)


@router.get(
    "/versions/{version_id}/organisation",
    response_model=ConfigurationOrganisationSnapshot,
)
async def organisation_snapshot(
    version_id: UUID,
    actor: CurrentActor,
    service: ConfigurationQueryDependency,
    at: Annotated[AwareDatetime | None, Query()] = None,
) -> ConfigurationOrganisationSnapshot:
    return await service.organisation(actor, version_id, at=at)


@router.get("/active", response_model=ConfigurationVersionDetail)
async def active_version(
    actor: CurrentActor,
    service: ConfigurationQueryDependency,
) -> ConfigurationVersionDetail:
    return await service.active(actor)


@router.get("/workflow-definitions", response_model=ApprovedWorkflowDefinitionList)
async def workflow_definitions(
    actor: CurrentActor,
    service: ConfigurationQueryDependency,
) -> ApprovedWorkflowDefinitionList:
    return await service.workflow_definitions(actor)
