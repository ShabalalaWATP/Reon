"""Transactional request-event projection facade and repair boundary."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.models import ServiceRequest
from mist_service.notification_rule_serialisation import deserialise_rule
from mist_service.operational_analytics_projection import (
    project_request_operational_event,
)
from mist_service.repositories.notification_projection import (
    SqlAlchemyNotificationProjectionRepository,
)
from mist_service.repositories.notifications import SqlAlchemyNotificationRepository
from mist_service.request_action_projection import project_request_action
from mist_service.request_event_models import RequestEvent
from mist_service.request_notification_projection import (
    publish_request_notification,
    reconcile_pending_notifications,
)
from mist_service.services.notification_service import NotificationService

__all__ = [
    "NotificationProjectionBatchFailed",
    "NotificationProjectionReconciler",
    "project_request_event",
    "reconcile_pending_notifications",
]


class NotificationProjectionBatchFailed(RuntimeError):
    """Report a content-free aggregate after individual failures are persisted."""

    def __init__(self, failure_count: int) -> None:
        super().__init__(f"{failure_count} notification projection event(s) failed.")


@dataclass(frozen=True, slots=True)
class _ProjectionOutcome:
    attempted: bool
    failed: bool = False


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
        attempted = False
        failures = 0
        for _ in range(self._batch_size):
            outcome = await self._reconcile_next()
            if not outcome.attempted:
                break
            attempted = True
            failures += int(outcome.failed)
        if failures:
            raise NotificationProjectionBatchFailed(failures)
        return attempted

    async def _reconcile_next(self) -> _ProjectionOutcome:
        event_id: UUID | None = None
        attempted_at = _utc_now()
        try:
            async with self._sessions() as session, session.begin():
                projection = SqlAlchemyNotificationProjectionRepository(session)
                events = await projection.pending_events(
                    limit=1,
                    available_at=attempted_at,
                )
                if not events:
                    return _ProjectionOutcome(attempted=False)
                event = events[0]
                event_id = event.id
                await projection.project_event(
                    event.id,
                    [deserialise_rule(rule) for rule in event.audience],
                    projected_at=attempted_at,
                )
        except Exception as error:
            if event_id is None:
                raise
            await self._record_failure(event_id, error)
            return _ProjectionOutcome(attempted=True, failed=True)
        return _ProjectionOutcome(attempted=True)

    async def _record_failure(
        self,
        event_id: UUID,
        error: Exception,
    ) -> None:
        async with self._sessions() as session, session.begin():
            service = NotificationService(
                SqlAlchemyNotificationRepository(session),
                SqlAlchemyNotificationProjectionRepository(session),
            )
            await service.projection_failed(
                event_id,
                type(error).__name__,
                attempted_at=_utc_now(),
            )


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def project_request_event(
    session: AsyncSession, event: RequestEvent, request: ServiceRequest
) -> None:
    await project_request_action(session, event, request)
    await publish_request_notification(session, event, request)
    await project_request_operational_event(session, event, request)
