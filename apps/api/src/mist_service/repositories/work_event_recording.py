"""Audience-safe supplementary events for human workflow decisions."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import Actor
from mist_service.models import ServiceRequest
from mist_service.repositories.event_store import append_request_event
from mist_service.request_event_audience import RequestEventAudience
from mist_service.schemas.work import CompletionPayload, ProgressRequest


async def append_routing_note(
    session: AsyncSession,
    request: ServiceRequest,
    actor: Actor,
    payload: CompletionPayload,
    details: dict[str, Any],
) -> None:
    """Record an optional routing note without exposing it to the Customer."""

    if not isinstance(payload, ProgressRequest) or not payload.note:
        return
    await append_request_event(
        session,
        request_id=request.id,
        actor_id=actor.id,
        event_type="routing_message",
        message=f"Routing message: {payload.note}",
        prior_status=None,
        next_status=None,
        audience=RequestEventAudience.STAFF_ONLY,
        details=details,
    )
