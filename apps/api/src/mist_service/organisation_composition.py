"""Composition boundary for organisation directory and tracking operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.repositories.organisation import SqlAlchemyOrganisationRepository
from mist_service.repositories.organisation_tracking_repository import (
    SqlAlchemyOrganisationTrackingRepository,
)
from mist_service.services.organisation_service import OrganisationService


def build_organisation_service(session: AsyncSession) -> OrganisationService:
    return OrganisationService(
        SqlAlchemyOrganisationRepository(session),
        SqlAlchemyOrganisationTrackingRepository(session),
    )
