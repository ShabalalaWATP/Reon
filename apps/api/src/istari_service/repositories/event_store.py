"""Append-only, hash-linked request event persistence."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.analytics_projection import project_request_analytics
from istari_service.audit import (
    AUDIT_KEY_INFO,
    canonical_anchor_mac,
    canonical_event_hash,
    verify_event_chain,
)
from istari_service.audit_types import AuditEventEvidence, validate_audit_details
from istari_service.models import RequestEvent, RequestStatus, ServiceRequest
from istari_service.request_event_projection import project_request_event


async def append_request_event(
    session: AsyncSession,
    *,
    request_id: UUID,
    actor_id: UUID | None,
    event_type: str,
    message: str,
    prior_status: RequestStatus | None,
    next_status: RequestStatus | None,
    details: Mapping[str, object] | None = None,
) -> RequestEvent:
    """Append one event linked to the latest hash for this request."""

    request = await session.scalar(
        select(ServiceRequest).where(ServiceRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise LookupError("request audit anchor is unavailable")
    previous_hash = request.audit_head_hash
    audit_key = audit_key_for_session(session)
    created_at = datetime.now(UTC)
    safe_details = validate_audit_details(details)
    event_hash = canonical_event_hash(
        request_id=request_id,
        event_type=event_type,
        message=message,
        actor_id=actor_id,
        created_at=created_at,
        previous_hash=previous_hash,
        audit_key=audit_key,
        prior_status=prior_status,
        next_status=next_status,
        details=safe_details,
    )
    event = RequestEvent(
        request_id=request_id,
        actor_user_id=actor_id,
        type=event_type,
        message=message,
        prior_status=prior_status,
        next_status=next_status,
        details=safe_details,
        previous_hash=previous_hash,
        event_hash=event_hash,
        created_at=created_at,
    )
    session.add(event)
    request.audit_event_count += 1
    request.audit_head_hash = event_hash
    request.audit_anchor_mac = canonical_anchor_mac(
        request_id=request.id,
        event_count=request.audit_event_count,
        head_hash=event_hash,
        audit_key=audit_key,
    )
    await session.flush()
    await project_request_analytics(session, request_id)
    await project_request_event(session, event, request)
    return event


async def verify_request_event_integrity(
    session: AsyncSession,
    request_id: UUID,
) -> bool:
    """Compare the complete stored chain with its request-owned head and count."""

    request = await session.get(ServiceRequest, request_id)
    if request is None:
        return False
    audit_key = audit_key_for_session(session)
    if request.audit_event_count == 0:
        if request.audit_head_hash is not None or request.audit_anchor_mac is not None:
            return False
    elif (
        request.audit_head_hash is None
        or request.audit_anchor_mac is None
        or not hmac.compare_digest(
            request.audit_anchor_mac,
            canonical_anchor_mac(
                request_id=request.id,
                event_count=request.audit_event_count,
                head_hash=request.audit_head_hash,
                audit_key=audit_key,
            ),
        )
    ):
        return False
    events = (
        await session.scalars(
            select(RequestEvent)
            .where(RequestEvent.request_id == request_id)
            .order_by(RequestEvent.created_at, RequestEvent.id)
        )
    ).all()
    chain = [
        AuditEventEvidence(
            request_id=event.request_id,
            event_type=event.type,
            message=event.message,
            actor_id=event.actor_user_id,
            created_at=event.created_at,
            previous_hash=event.previous_hash,
            prior_status=event.prior_status,
            next_status=event.next_status,
            details=event.details,
            event_hash=event.event_hash,
        )
        for event in events
    ]
    return verify_event_chain(
        chain,
        audit_key=audit_key,
        expected_head_hash=request.audit_head_hash,
        expected_count=request.audit_event_count,
    )


def audit_key_for_session(session: AsyncSession) -> bytes:
    key = session.info.get(AUDIT_KEY_INFO)
    if not isinstance(key, bytes) or len(key) < 32:
        raise RuntimeError("a valid audit HMAC key is required")
    return key
