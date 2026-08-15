"""SQLAlchemy adapter for exact-root management grant authorisation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.management_models import ManagementAction
from mist_service.repositories.management import resolve_management_scope


class SqlAlchemyExactManagementScopeAuthorisation:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def authorises_exact_root(
        self,
        *,
        actor_id: UUID,
        grant_id: UUID,
        unit_id: UUID,
        action: ManagementAction,
        lock: bool,
    ) -> bool:
        scope = await resolve_management_scope(
            self._session,
            subject_user_id=actor_id,
            grant_id=grant_id,
            target_unit_id=unit_id,
            action=action,
            lock=lock,
        )
        return scope is not None and scope.root_unit_id == unit_id
