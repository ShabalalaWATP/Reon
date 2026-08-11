"""Transactional request leadership and contributor persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.models import User
from istari_service.request_participant_models import (
    RequestParticipant,
    RequestParticipantRole,
)
from istari_service.schemas.requests import RequesterView


async def replace_request_participants(
    session: AsyncSession,
    *,
    request_id: UUID,
    lead_id: UUID,
    contributor_ids: list[UUID],
    actor_id: UUID,
    reason: str,
) -> None:
    now = datetime.now(UTC)
    current = list(
        await session.scalars(
            select(RequestParticipant)
            .where(
                RequestParticipant.request_id == request_id,
                RequestParticipant.ended_at.is_(None),
            )
            .with_for_update()
        )
    )
    for participant in current:
        participant.ended_at = now
        participant.ended_by_user_id = actor_id
        participant.end_reason = reason.strip()
        participant.version += 1
    session.add(
        RequestParticipant(
            request_id=request_id,
            user_id=lead_id,
            role=RequestParticipantRole.LEAD,
            assigned_by_user_id=actor_id,
            reason=reason.strip(),
            effective_from=now,
        )
    )
    session.add_all(
        RequestParticipant(
            request_id=request_id,
            user_id=user_id,
            role=RequestParticipantRole.CONTRIBUTOR,
            assigned_by_user_id=actor_id,
            reason=reason.strip(),
            effective_from=now,
        )
        for user_id in contributor_ids
    )
    await session.flush()


async def active_participant_ids(
    session: AsyncSession, request_id: UUID
) -> frozenset[UUID]:
    return frozenset(
        await session.scalars(
            select(RequestParticipant.user_id).where(
                RequestParticipant.request_id == request_id,
                RequestParticipant.ended_at.is_(None),
            )
        )
    )


async def active_contributor_views(
    session: AsyncSession, request_id: UUID
) -> list[RequesterView]:
    rows = (
        await session.execute(
            select(User.id, User.display_name)
            .join(RequestParticipant, RequestParticipant.user_id == User.id)
            .where(
                RequestParticipant.request_id == request_id,
                RequestParticipant.role == RequestParticipantRole.CONTRIBUTOR,
                RequestParticipant.ended_at.is_(None),
                User.is_active.is_(True),
            )
            .order_by(User.display_name, User.id)
        )
    ).all()
    return [RequesterView(id=user_id, display_name=name) for user_id, name in rows]
