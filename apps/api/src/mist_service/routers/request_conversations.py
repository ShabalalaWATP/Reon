"""Authenticated structured-conversation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from mist_service.conversation_composition import (
    build_request_conversation_service,
)
from mist_service.dependencies import CurrentActor, DatabaseSession, MutationActor
from mist_service.schemas.conversations import (
    ConversationMessageCreate,
    ConversationMutationResult,
    ConversationReadResult,
    ConversationView,
    ConversationWorkspace,
)

router = APIRouter(prefix="/requests", tags=["request-conversations"])


@router.get("/{request_id}/conversations", response_model=ConversationWorkspace)
async def get_conversations(
    request_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=500),
    message_limit: int = Query(default=50, alias="messageLimit", ge=1, le=100),
) -> ConversationWorkspace:
    return await build_request_conversation_service(session).workspace(
        actor,
        request_id,
        limit=limit,
        cursor=cursor,
        message_limit=message_limit,
    )


@router.get(
    "/{request_id}/conversations/{conversation_id}",
    response_model=ConversationView,
)
async def get_conversation(
    request_id: UUID,
    conversation_id: UUID,
    actor: CurrentActor,
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=500),
) -> ConversationView:
    return await build_request_conversation_service(session).conversation_page(
        actor,
        request_id,
        conversation_id,
        limit=limit,
        cursor=cursor,
    )


@router.post(
    "/{request_id}/conversations/messages",
    response_model=ConversationMutationResult,
)
async def post_conversation_message(
    request_id: UUID,
    command: ConversationMessageCreate,
    actor: MutationActor,
    session: DatabaseSession,
) -> ConversationMutationResult:
    return await build_request_conversation_service(session).post_message(
        actor, request_id, command
    )


@router.post(
    "/{request_id}/conversations/{conversation_id}/read",
    response_model=ConversationReadResult,
)
async def mark_conversation_read(
    request_id: UUID,
    conversation_id: UUID,
    actor: MutationActor,
    session: DatabaseSession,
) -> ConversationReadResult:
    return await build_request_conversation_service(session).mark_read(
        actor, request_id, conversation_id
    )
