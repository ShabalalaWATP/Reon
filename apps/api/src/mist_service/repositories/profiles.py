"""Persistence adapter for the authenticated user's own profile."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.errors import ObjectNotFound, StaleVersion
from mist_service.models import User
from mist_service.schemas.profiles import ProfileUpdate, ProfileView


class SqlAlchemyProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID, *, lock: bool = False) -> User:
        query = select(User).where(User.id == user_id, User.is_active.is_(True))
        if lock:
            query = query.with_for_update()
        user = await self._session.scalar(query)
        if user is None:
            raise ObjectNotFound()
        return user

    async def view(self, user_id: UUID) -> ProfileView:
        return self._view(await self.get(user_id))

    async def update(self, user_id: UUID, command: ProfileUpdate) -> ProfileView:
        user = await self.get(user_id, lock=True)
        if user.version != command.expected_version:
            raise StaleVersion()
        user.profile_team = command.profile_team
        user.rank_or_grade = command.rank_or_grade
        user.service_number = command.service_number
        user.additional_information = command.additional_information
        user.skills = command.skills
        user.version += 1
        await self._session.flush()
        return self._view(user)

    @staticmethod
    def _view(user: User) -> ProfileView:
        return ProfileView(
            user_id=user.id,
            name=user.display_name,
            username=user.username,
            email=user.email,
            role=user.role,
            profile_team=user.profile_team,
            rank_or_grade=user.rank_or_grade,
            service_number=user.service_number,
            additional_information=user.additional_information,
            skills=user.skills,
            version=user.version,
        )
