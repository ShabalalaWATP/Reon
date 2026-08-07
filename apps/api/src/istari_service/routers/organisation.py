"""Authenticated organisation and metadata-only tracking routes."""

from __future__ import annotations

from fastapi import APIRouter

from istari_service.dependencies import CurrentActor, DatabaseSession
from istari_service.repositories.organisation import SqlAlchemyOrganisationRepository
from istari_service.schemas.organisation import (
    OrganisationUnitList,
    TrackedRequestList,
)
from istari_service.services.organisation_service import OrganisationService

router = APIRouter(tags=["organisation"])


def _service(session: DatabaseSession) -> OrganisationService:
    return OrganisationService(SqlAlchemyOrganisationRepository(session))


@router.get("/organisation/units", response_model=OrganisationUnitList)
async def list_organisation_units(
    actor: CurrentActor,
    session: DatabaseSession,
) -> OrganisationUnitList:
    return OrganisationUnitList(items=await _service(session).list_units(actor))


@router.get("/tracked-requests", response_model=TrackedRequestList)
async def list_tracked_requests(
    actor: CurrentActor,
    session: DatabaseSession,
) -> TrackedRequestList:
    return TrackedRequestList(
        items=await _service(session).list_tracked_requests(actor)
    )
