"""Bounded public rendering helpers for request conversations."""

from __future__ import annotations

import hashlib
from uuid import UUID

from istari_service.conversation_models import (
    RequestConversation,
    RequestConversationMessage,
)
from istari_service.request_event_models import RequestEvent
from istari_service.schemas.conversations import (
    ConversationMessageView,
    ConversationView,
)
from istari_service.schemas.organisation import TrackedRequestEvent
from istari_service.services.conversation_ports import ConversationPageReader


async def load_conversation_view(
    pages: ConversationPageReader,
    conversation: RequestConversation,
    actor_id: UUID,
    limit: int,
) -> ConversationView:
    page = await pages.messages(conversation.id, limit=limit)
    unread = await pages.unread_counts([conversation.id], actor_id)
    return conversation_view(
        conversation,
        actor_id,
        page.items,
        page.next_cursor,
        unread_count=unread.get(conversation.id, 0),
    )


def conversation_view(
    conversation: RequestConversation,
    actor_id: UUID,
    messages: list[RequestConversationMessage],
    messages_next_cursor: str | None,
    *,
    unread_count: int,
) -> ConversationView:
    rendered: list[ConversationMessageView] = []
    for message in messages:
        delivery = next(
            (item for item in message.deliveries if item.recipient_user_id == actor_id),
            None,
        )
        is_read = delivery is None or delivery.read_at is not None
        rendered.append(
            ConversationMessageView(
                id=message.id,
                sender_user_id=message.sender_user_id,
                sender_display_name=message.sender.display_name,
                sender_role=message.sender_role,
                body=message.body,
                reply_to_message_id=message.reply_to_message_id,
                created_at=message.created_at,
                is_read=is_read,
            )
        )
    return ConversationView(
        id=conversation.id,
        subject=conversation.subject,
        target_type=conversation.target_type,
        target_unit_id=conversation.target_unit_id,
        target_label=conversation.target_label,
        visibility=conversation.visibility,
        created_at=conversation.created_at,
        messages=rendered,
        unread_count=unread_count,
        messages_next_cursor=messages_next_cursor,
    )


def conversation_body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def tracked_event_view(event: RequestEvent, actor_name: str) -> TrackedRequestEvent:
    return TrackedRequestEvent(
        id=event.id,
        type=event.type,
        message=event.message,
        actor_display_name=actor_name,
        prior_status=event.prior_status,
        next_status=event.next_status,
        created_at=event.created_at,
    )
