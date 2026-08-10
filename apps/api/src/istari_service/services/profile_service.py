"""Self-profile use cases."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from istari_service.domain import Actor
from istari_service.schemas.profiles import ProfileUpdate, ProfileView


class ProfileRepository(Protocol):
    async def view(self, user_id: UUID) -> ProfileView: ...
    async def update(self, user_id: UUID, command: ProfileUpdate) -> ProfileView: ...


class ProfileService:
    def __init__(self, repository: ProfileRepository) -> None:
        self._repository = repository

    async def get(self, actor: Actor) -> ProfileView:
        return await self._repository.view(actor.id)

    async def update(self, actor: Actor, command: ProfileUpdate) -> ProfileView:
        return await self._repository.update(actor.id, command)
