"""Pure recipient policy for request-conversation replies."""

from __future__ import annotations

from uuid import UUID

from istari_service.conversation_models import (
    ConversationTargetType,
    RequestConversation,
)
from istari_service.domain import Actor
from istari_service.models import ServiceRequest, UserRole
from istari_service.request_event_audience import RequestEventAudience


def reply_recipient_ids(
    actor: Actor,
    request: ServiceRequest,
    conversation: RequestConversation,
    target_recipients: set[UUID],
) -> set[UUID]:
    """Resolve bounded recipients without persistence or transport knowledge."""

    if conversation.visibility is RequestEventAudience.CUSTOMER_AND_STAFF:
        if actor.role is not UserRole.REQUESTER:
            return {request.requester_id}
        if conversation.target_type is ConversationTargetType.CURRENT_OWNER:
            return target_recipients
        return {conversation.opened_by_user_id}
    return target_recipients
