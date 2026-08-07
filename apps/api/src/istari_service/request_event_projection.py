"""Transactional request-event projection facade and repair boundary."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from istari_service.models import RequestEvent, ServiceRequest
from istari_service.operational_analytics_projection import (
    project_request_operational_event,
)
from istari_service.request_action_projection import project_request_action
from istari_service.request_notification_projection import (
    publish_request_notification,
    reconcile_pending_notifications,
)

__all__ = [
    "NotificationProjectionReconciler",
    "project_request_event",
    "reconcile_pending_notifications",
]


class NotificationProjectionReconciler:
    """Repair one bounded batch of durable notification events."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        batch_size: int = 100,
    ) -> None:
        self._sessions = sessions
        self._batch_size = batch_size

    async def reconcile_once(self) -> bool:
        async with self._sessions() as session, session.begin():
            projected = await reconcile_pending_notifications(
                session,
                limit=self._batch_size,
            )
        return projected > 0


async def project_request_event(
    session: AsyncSession, event: RequestEvent, request: ServiceRequest
) -> None:
    await project_request_action(session, event, request)
    await publish_request_notification(session, event, request)
    await project_request_operational_event(session, event, request)
