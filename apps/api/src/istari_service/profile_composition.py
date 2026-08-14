"""Composition boundary for authenticated self-profile operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.repositories.profiles import SqlAlchemyProfileRepository
from istari_service.services.profile_service import ProfileService


def build_profile_service(session: AsyncSession) -> ProfileService:
    return ProfileService(SqlAlchemyProfileRepository(session))
