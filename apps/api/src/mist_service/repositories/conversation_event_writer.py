"""SQLAlchemy adapter for hash-linked conversation request events."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.models import RequestStatus
from mist_service.repositories.event_store import append_request_event
from mist_service.request_event_audience import RequestEventAudience
from mist_service.request_event_models import RequestEvent


class SqlAlchemyRequestEventWriter:
    """Persist request events through the existing hash-linked event store."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        request_id: UUID,
        actor_id: UUID | None,
        event_type: str,
        message: str,
        prior_status: RequestStatus | None,
        next_status: RequestStatus | None,
        audience: RequestEventAudience | None = None,
        details: Mapping[str, object] | None = None,
    ) -> RequestEvent:
        return await append_request_event(
            self._session,
            request_id=request_id,
            actor_id=actor_id,
            event_type=event_type,
            message=message,
            prior_status=prior_status,
            next_status=next_status,
            audience=audience,
            details=details,
        )
