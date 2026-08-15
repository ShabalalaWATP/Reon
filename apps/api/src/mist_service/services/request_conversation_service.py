"""Structured, immutable request conversation use cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from mist_service.conversation_models import (
    ConversationTargetType,
    RequestConversation,
    RequestConversationMessage,
)
from mist_service.domain import Actor
from mist_service.errors import InvalidAction, ObjectNotFound
from mist_service.models import ServiceRequest, UserRole
from mist_service.projection_pagination import decode_cursor
from mist_service.request_event_audience import RequestEventAudience
from mist_service.schemas.conversations import (
    ConversationMessageCreate,
    ConversationMutationResult,
    ConversationReadResult,
    ConversationView,
    ConversationWorkspace,
)
from mist_service.services.conversation_access import (
    ConversationAccess,
    ResolvedConversationTarget,
)
from mist_service.services.conversation_limits import (
    MUTATION_MESSAGE_LIMIT,
    enforce_conversation_admission,
)
from mist_service.services.conversation_ports import (
    ConversationPageReader,
    ConversationStore,
    RequestEventWriter,
)
from mist_service.services.conversation_recipient_policy import (
    reply_recipient_ids,
)
from mist_service.services.conversation_rendering import (
    conversation_body_hash,
    conversation_view,
    load_conversation_view,
    tracked_event_view,
)


class RequestConversationService:
    def __init__(
        self,
        repository: ConversationStore,
        pages: ConversationPageReader,
        access: ConversationAccess,
        events: RequestEventWriter,
    ) -> None:
        self._repository = repository
        self._pages = pages
        self._access = access
        self._events = events

    async def workspace(
        self,
        actor: Actor,
        request_id: UUID,
        *,
        limit: int = 20,
        cursor: str | None = None,
        message_limit: int = 50,
    ) -> ConversationWorkspace:
        request = await self._access.authorised_request(actor, request_id)
        scope = await self._access.audience_scope(actor, request)
        page = await self._pages.conversations(
            request.id,
            customer_only=scope.customer_only,
            allowed_targets=set(scope.allowed_targets),
            route_unit_ids=set(scope.route_unit_ids),
            limit=limit,
            cursor=_cursor(cursor),
        )
        conversation_ids = [item.id for item in page.items]
        message_pages = await self._pages.message_pages(
            conversation_ids, limit=message_limit
        )
        unread_counts = await self._pages.unread_counts(conversation_ids, actor.id)
        return ConversationWorkspace(
            allowed_targets=await self._access.allowed_targets(actor, request),
            conversations=[
                conversation_view(
                    item,
                    actor.id,
                    message_pages[item.id].items,
                    message_pages[item.id].next_cursor,
                    unread_count=unread_counts.get(item.id, 0),
                )
                for item in page.items
            ],
            conversations_next_cursor=page.next_cursor,
        )

    async def conversation_page(
        self,
        actor: Actor,
        request_id: UUID,
        conversation_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ConversationView:
        request = await self._access.authorised_request(actor, request_id)
        conversation = await self._repository.conversation(request.id, conversation_id)
        if conversation is None or not await self._access.can_access_conversation(
            actor, request, conversation
        ):
            raise ObjectNotFound()
        messages = await self._pages.messages(
            conversation.id, limit=limit, cursor=_cursor(cursor)
        )
        unread = await self._pages.unread_counts([conversation.id], actor.id)
        return conversation_view(
            conversation,
            actor.id,
            messages.items,
            messages.next_cursor,
            unread_count=unread.get(conversation.id, 0),
        )

    async def post_message(
        self,
        actor: Actor,
        request_id: UUID,
        command: ConversationMessageCreate,
        *,
        legacy_event_message: str | None = None,
        legacy_event_type: str | None = None,
        legacy_event_audience: RequestEventAudience | None = None,
    ) -> ConversationMutationResult:
        request = await self._access.authorised_request(actor, request_id)
        locked_request = await self._repository.lock_request(request.id)
        if locked_request is None:  # pragma: no cover - restricted deletion
            raise ObjectNotFound()
        request = locked_request
        request = await self._access.authorised_request(actor, request.id)
        repeated = await self._repository.mutation_message(
            actor.id, command.client_mutation_id
        )
        if repeated is not None:
            return await self._idempotent_result(actor, request, command, repeated)
        await enforce_conversation_admission(
            self._pages,
            request.id,
            actor.id,
            creates_conversation=command.conversation_id is None,
        )
        if command.conversation_id is None:
            conversation, target = await self._new_conversation(actor, request, command)
        else:
            conversation = await self._reply_conversation(
                actor, request.id, command.conversation_id
            )
            target = ResolvedConversationTarget(
                conversation.target_type,
                conversation.target_unit_id,
                conversation.target_label,
            )
        reply_to = None
        if command.reply_to_message_id is not None:
            reply_to = await self._repository.message_in_conversation(
                conversation.id, command.reply_to_message_id
            )
        if command.reply_to_message_id is not None and reply_to is None:
            raise ObjectNotFound()
        if reply_to is not None and reply_to.reply_to_message_id is not None:
            raise InvalidAction("Replies may reference only a top-level message.")

        message_id = uuid4()
        body_hash = conversation_body_hash(command.body)
        event = await self._events.append(
            request_id=request.id,
            actor_id=actor.id,
            event_type=legacy_event_type or "REQUEST_MESSAGE_POSTED",
            message=legacy_event_message
            or f"Conversation message recorded for {target.label}.",
            prior_status=request.status,
            next_status=request.status,
            audience=legacy_event_audience or conversation.visibility,
            details={
                "conversationId": str(conversation.id),
                "messageId": str(message_id),
                "bodySha256": body_hash,
                "targetType": target.type.value,
                "targetUnitId": str(target.unit_id) if target.unit_id else None,
            },
        )
        message = RequestConversationMessage(
            id=message_id,
            conversation_id=conversation.id,
            sender_user_id=actor.id,
            sender_role=actor.role,
            body=command.body,
            body_sha256=body_hash,
            reply_to_message_id=command.reply_to_message_id,
            client_mutation_id=command.client_mutation_id,
            request_event_id=event.id,
        )
        target_recipients = await self._access.recipient_ids(request, target)
        recipients = reply_recipient_ids(
            actor, request, conversation, target_recipients
        )
        if not recipients:
            raise InvalidAction("That conversation target has no current recipients.")
        await self._repository.add_message(
            conversation if command.conversation_id is None else None,
            message,
            recipients,
        )
        stored = await self._repository.conversation(request.id, conversation.id)
        if stored is None:  # pragma: no cover - transaction invariant
            raise RuntimeError("conversation was not persisted")
        return ConversationMutationResult(
            conversation=await load_conversation_view(
                self._pages, stored, actor.id, MUTATION_MESSAGE_LIMIT
            ),
            event=tracked_event_view(event, actor.display_name),
        )

    async def mark_read(
        self, actor: Actor, request_id: UUID, conversation_id: UUID
    ) -> ConversationReadResult:
        request = await self._access.authorised_request(actor, request_id)
        conversation = await self._repository.conversation(request_id, conversation_id)
        if conversation is None or not await self._access.can_access_conversation(
            actor, request, conversation
        ):
            raise ObjectNotFound()
        await self._repository.mark_read(conversation.id, actor.id, datetime.now(UTC))
        return ConversationReadResult(conversation_id=conversation.id, unread_count=0)

    async def _new_conversation(
        self,
        actor: Actor,
        request: ServiceRequest,
        command: ConversationMessageCreate,
    ) -> tuple[RequestConversation, ResolvedConversationTarget]:
        if command.target_type is None:  # pragma: no cover - schema invariant
            raise InvalidAction("A target is required for a new conversation.")
        target = await self._access.resolve_target(
            actor, request, command.target_type, command.target_unit_id
        )
        visibility = (
            RequestEventAudience.CUSTOMER_AND_STAFF
            if actor.role is UserRole.REQUESTER
            or target.type is ConversationTargetType.CUSTOMER
            else RequestEventAudience.STAFF_ONLY
        )
        conversation = RequestConversation(
            id=uuid4(),
            request_id=request.id,
            opened_by_user_id=actor.id,
            target_type=target.type,
            target_unit_id=target.unit_id,
            target_label=target.label,
            subject=command.subject or f"Conversation with {target.label}",
            visibility=visibility,
        )
        return conversation, target

    async def _reply_conversation(
        self, actor: Actor, request_id: UUID, conversation_id: UUID
    ) -> RequestConversation:
        conversation = await self._repository.conversation(request_id, conversation_id)
        request = await self._access.authorised_request(actor, request_id)
        if conversation is None or not await self._access.can_access_conversation(
            actor, request, conversation
        ):
            raise ObjectNotFound()
        return conversation

    async def _idempotent_result(
        self,
        actor: Actor,
        request: ServiceRequest,
        command: ConversationMessageCreate,
        message: RequestConversationMessage,
    ) -> ConversationMutationResult:
        conversation = message.conversation
        first_message_id = await self._repository.first_message_id(conversation.id)
        new_thread_retry = command.conversation_id is None and (
            first_message_id == message.id
            and command.target_type is conversation.target_type
            and command.target_unit_id == conversation.target_unit_id
            and (command.subject is None or command.subject == conversation.subject)
        )
        reply_retry = command.conversation_id == conversation.id
        if (
            conversation.request_id != request.id
            or conversation_body_hash(command.body) != message.body_sha256
            or command.reply_to_message_id != message.reply_to_message_id
            or not (new_thread_retry or reply_retry)
        ):
            raise InvalidAction(
                "The client mutation ID belongs to a different message."
            )
        if not await self._access.can_access_conversation(actor, request, conversation):
            raise ObjectNotFound()
        return ConversationMutationResult(
            conversation=await load_conversation_view(
                self._pages, conversation, actor.id, MUTATION_MESSAGE_LIMIT
            ),
            event=tracked_event_view(message.request_event, actor.display_name),
        )


def _cursor(value: str | None) -> tuple[datetime, UUID] | None:
    return (
        decode_cursor(value, message="The conversation cursor is invalid.")
        if value is not None
        else None
    )
