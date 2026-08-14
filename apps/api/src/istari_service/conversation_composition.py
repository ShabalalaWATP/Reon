"""Composition boundary for structured request conversations."""

from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.repositories.conversation_event_writer import (
    SqlAlchemyRequestEventWriter,
)
from istari_service.repositories.conversation_pages import (
    RequestConversationPageRepository,
)
from istari_service.repositories.request_conversations import (
    RequestConversationRepository,
)
from istari_service.repositories.request_coordination import (
    RequestCoordinationRepository,
)
from istari_service.services.conversation_access import ConversationAccess
from istari_service.services.request_conversation_service import (
    RequestConversationService,
)


def build_request_conversation_service(
    session: AsyncSession,
) -> RequestConversationService:
    """Wire application ports to SQLAlchemy adapters for one request transaction."""

    repository = RequestConversationRepository(session)
    pages = RequestConversationPageRepository(session)
    access = ConversationAccess(repository, RequestCoordinationRepository(session))
    return RequestConversationService(
        repository=repository,
        pages=pages,
        access=access,
        events=SqlAlchemyRequestEventWriter(session),
    )
