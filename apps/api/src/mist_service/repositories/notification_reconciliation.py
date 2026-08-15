"""SQLAlchemy adapter for pending notification reconciliation."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.request_notification_projection import (
    reconcile_pending_notifications,
)


class SqlAlchemyNotificationReconciler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reconcile_pending(self) -> int:
        return await reconcile_pending_notifications(self._session)
