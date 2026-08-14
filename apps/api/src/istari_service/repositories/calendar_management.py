"""SQLAlchemy adapter for exact-team calendar management authority."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.management_models import ManagementAction
from istari_service.repositories.management import resolve_management_scope


class SqlAlchemyCalendarManagement:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_authority(
        self,
        actor: Actor,
        team_id: UUID,
        grant_id: UUID,
        action: ManagementAction,
    ) -> bool:
        scope = await resolve_management_scope(
            self._session,
            subject_user_id=actor.id,
            grant_id=grant_id,
            target_unit_id=team_id,
            action=action,
            lock=True,
        )
        return scope is not None and scope.root_unit_id == team_id
