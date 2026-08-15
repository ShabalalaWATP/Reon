"""Operational admission and rendering limits for request conversations."""

from uuid import UUID

from mist_service.errors import InvalidAction
from mist_service.services.conversation_ports import ConversationPageReader

CONVERSATIONS_PER_REQUEST = 100
MESSAGES_PER_REQUEST = 2_000
MESSAGES_PER_AUTHOR_PER_REQUEST = 500
MUTATION_MESSAGE_LIMIT = 100


async def enforce_conversation_admission(
    pages: ConversationPageReader,
    request_id: UUID,
    actor_id: UUID,
    *,
    creates_conversation: bool,
) -> None:
    conversations, request_messages, actor_messages = await pages.admission_counts(
        request_id, actor_id
    )
    limit_reached = (
        (creates_conversation and conversations >= CONVERSATIONS_PER_REQUEST)
        or request_messages >= MESSAGES_PER_REQUEST
        or actor_messages >= MESSAGES_PER_AUTHOR_PER_REQUEST
    )
    if limit_reached:
        raise InvalidAction("The conversation admission limit has been reached.")
