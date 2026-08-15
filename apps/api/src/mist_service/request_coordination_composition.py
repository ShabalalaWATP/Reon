"""Composition boundary for legacy request-coordination endpoints."""

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.conversation_composition import (
    build_request_conversation_service,
)
from mist_service.repositories.conversation_event_writer import (
    SqlAlchemyRequestEventWriter,
)
from mist_service.repositories.request_coordination import (
    RequestCoordinationRepository,
)
from mist_service.services.request_coordination_service import (
    RequestCoordinationService,
)


def request_coordination_service(session: AsyncSession) -> RequestCoordinationService:
    """Wire coordination use cases to transaction-scoped SQLAlchemy adapters."""

    repository = RequestCoordinationRepository(session)
    return RequestCoordinationService(
        requests=repository,
        access=repository,
        returns=repository,
        events=SqlAlchemyRequestEventWriter(session),
        conversations=build_request_conversation_service(session),
    )
