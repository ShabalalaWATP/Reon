"""Page records shared by conversation ports and persistence adapters."""

from __future__ import annotations

from dataclasses import dataclass

from istari_service.conversation_models import (
    RequestConversation,
    RequestConversationMessage,
)


@dataclass(frozen=True, slots=True)
class ConversationPage:
    items: list[RequestConversation]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class MessagePage:
    items: list[RequestConversationMessage]
    next_cursor: str | None
