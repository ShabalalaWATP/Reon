"""Locked persistence rules for append-only production clarifications."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.clarification_models import (
    ClarificationMessage,
    ClarificationMessageKind,
    ClarificationStatus,
    ClarificationThread,
)
from mist_service.domain import Actor
from mist_service.errors import InvalidAction
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.request_participant_models import RequestParticipant
from mist_service.schemas.work import ProvideClarification, RequestClarification


async def validate_clarification_effect(
    session: AsyncSession,
    request: ServiceRequest,
    actor: Actor,
    payload: RequestClarification | ProvideClarification,
) -> None:
    if isinstance(payload, RequestClarification):
        open_id = await session.scalar(
            select(ClarificationThread.id).where(
                ClarificationThread.request_id == request.id,
                ClarificationThread.status == ClarificationStatus.OPEN,
            )
        )
        if (
            request.status
            not in {RequestStatus.IN_PROGRESS, RequestStatus.REWORK_REQUIRED}
            or not await _is_assigned_analyst(session, request, actor)
            or payload.response_deadline < datetime.now(UTC).date()
            or payload.response_deadline > request.required_by
            or open_id is not None
        ):
            raise InvalidAction("The clarification cannot be opened.")
        return
    thread = await _open_thread(session, request.id, payload.thread_id)
    if (
        request.status is not RequestStatus.CUSTOMER_INFORMATION_REQUIRED
        or request.requester_id != actor.id
        or thread is None
        or thread.version != payload.expected_version
        or not await _thread_analyst_is_current(session, request, thread)
    ):
        raise InvalidAction("The clarification response is no longer current.")


async def apply_clarification_effect(
    session: AsyncSession,
    request: ServiceRequest,
    actor: Actor,
    payload: RequestClarification | ProvideClarification,
) -> None:
    if isinstance(payload, RequestClarification):
        await _create_thread(session, request, actor, payload)
        return
    thread = await _open_thread(session, request.id, payload.thread_id, lock=True)
    if thread is None or thread.version != payload.expected_version:
        raise InvalidAction("The clarification response is no longer current.")
    session.add(
        ClarificationMessage(
            thread_id=thread.id,
            actor_user_id=actor.id,
            sequence=2,
            kind=ClarificationMessageKind.RESPONSE,
            body=payload.information,
        )
    )
    thread.status = ClarificationStatus.ANSWERED
    thread.version += 1
    thread.closed_at = datetime.now(UTC)


async def withdraw_open_clarification(
    session: AsyncSession,
    request: ServiceRequest,
    actor: Actor,
    reason: str,
) -> None:
    if request.status is not RequestStatus.CUSTOMER_INFORMATION_REQUIRED:
        return
    thread = await session.scalar(
        select(ClarificationThread)
        .where(
            ClarificationThread.request_id == request.id,
            ClarificationThread.status == ClarificationStatus.OPEN,
        )
        .with_for_update()
    )
    if thread is None:
        raise InvalidAction("The clarification is no longer open.")
    session.add(
        ClarificationMessage(
            thread_id=thread.id,
            actor_user_id=actor.id,
            sequence=2,
            kind=ClarificationMessageKind.WITHDRAWAL,
            body=reason,
        )
    )
    thread.status = ClarificationStatus.WITHDRAWN
    thread.version += 1
    thread.closed_at = datetime.now(UTC)


async def _create_thread(
    session: AsyncSession,
    request: ServiceRequest,
    actor: Actor,
    payload: RequestClarification,
) -> None:
    latest_sequence = await session.scalar(
        select(func.max(ClarificationThread.sequence)).where(
            ClarificationThread.request_id == request.id
        )
    )
    if not await _is_assigned_analyst(session, request, actor):
        raise InvalidAction("An assigned Analyst is required.")
    thread = ClarificationThread(
        request_id=request.id,
        sequence=(latest_sequence or 0) + 1,
        requested_by_user_id=actor.id,
        assigned_specialist_id=actor.id,
        question=payload.question,
        reason=payload.reason,
        response_deadline=payload.response_deadline,
        status=ClarificationStatus.OPEN,
    )
    session.add(thread)
    await session.flush()
    session.add(
        ClarificationMessage(
            thread_id=thread.id,
            actor_user_id=actor.id,
            sequence=1,
            kind=ClarificationMessageKind.REQUEST,
            body=payload.question,
        )
    )


async def _is_assigned_analyst(
    session: AsyncSession, request: ServiceRequest, actor: Actor
) -> bool:
    if request.assigned_specialist_id == actor.id:
        return True
    participant_id = await session.scalar(
        select(RequestParticipant.user_id).where(
            RequestParticipant.request_id == request.id,
            RequestParticipant.user_id == actor.id,
            RequestParticipant.ended_at.is_(None),
        )
    )
    return participant_id == actor.id


async def _thread_analyst_is_current(
    session: AsyncSession,
    request: ServiceRequest,
    thread: ClarificationThread,
) -> bool:
    if thread.assigned_specialist_id == request.assigned_specialist_id:
        return True
    participant_id = await session.scalar(
        select(RequestParticipant.user_id).where(
            RequestParticipant.request_id == request.id,
            RequestParticipant.user_id == thread.assigned_specialist_id,
            RequestParticipant.ended_at.is_(None),
        )
    )
    return participant_id == thread.assigned_specialist_id


async def _open_thread(
    session: AsyncSession,
    request_id: UUID,
    thread_id: UUID,
    *,
    lock: bool = False,
) -> ClarificationThread | None:
    query = select(ClarificationThread).where(
        ClarificationThread.id == thread_id,
        ClarificationThread.request_id == request_id,
        ClarificationThread.status == ClarificationStatus.OPEN,
    )
    if lock:
        query = query.with_for_update()
    return cast(ClarificationThread | None, await session.scalar(query))
