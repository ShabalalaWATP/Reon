"""Authorised clarification read-model construction."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mist_service.clarification_models import (
    ClarificationMessage,
    ClarificationThread,
)
from mist_service.schemas.requests import (
    ClarificationMessageView,
    ClarificationThreadView,
    RequesterView,
)


async def clarification_views(
    session: AsyncSession,
    request_id: UUID,
) -> list[ClarificationThreadView]:
    threads = (
        await session.scalars(
            select(ClarificationThread)
            .options(
                selectinload(ClarificationThread.assigned_specialist),
                selectinload(ClarificationThread.messages).selectinload(
                    ClarificationMessage.actor
                ),
            )
            .where(ClarificationThread.request_id == request_id)
            .order_by(ClarificationThread.sequence)
        )
    ).all()
    return [
        ClarificationThreadView(
            id=thread.id,
            sequence=thread.sequence,
            question=thread.question,
            reason=thread.reason,
            response_deadline=thread.response_deadline,
            status=thread.status,
            version=thread.version,
            assigned_specialist=RequesterView(
                id=thread.assigned_specialist.id,
                display_name=thread.assigned_specialist.display_name,
            ),
            messages=[
                ClarificationMessageView(
                    id=message.id,
                    kind=message.kind,
                    body=message.body,
                    actor_display_name=message.actor.display_name,
                    created_at=message.created_at,
                )
                for message in thread.messages
            ],
            created_at=thread.created_at,
            closed_at=thread.closed_at,
        )
        for thread in threads
    ]
