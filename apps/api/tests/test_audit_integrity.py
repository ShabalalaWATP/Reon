"""Persisted audit-anchor regressions against raw event tampering."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import delete, select, update

from api_helpers import submit_request
from conftest import ApiHarness
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.repositories.event_store import verify_request_event_integrity
from mist_service.request_event_audience import RequestEventAudience
from mist_service.request_event_models import RequestEvent


async def test_audit_anchor_detects_status_tampering(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = UUID(await submit_request(harness))
    async with harness.sessions() as session, session.begin():
        assert await verify_request_event_integrity(session, request_id)
        await session.execute(
            update(RequestEvent)
            .where(RequestEvent.request_id == request_id)
            .values(next_status=RequestStatus.COMPLETED)
        )
        assert not await verify_request_event_integrity(session, request_id)


async def test_audit_anchor_detects_audience_tampering(
    api_harness: ApiHarness,
) -> None:
    request_id = UUID(await submit_request(api_harness))
    async with api_harness.sessions() as session, session.begin():
        event_id = await session.scalar(
            select(RequestEvent)
            .where(RequestEvent.request_id == request_id)
            .with_only_columns(RequestEvent.id)
        )
        assert event_id is not None
        await session.execute(
            update(RequestEvent)
            .where(RequestEvent.id == event_id)
            .values(audience=RequestEventAudience.STAFF_ONLY)
        )
        assert not await verify_request_event_integrity(session, request_id)


async def test_audit_anchor_detects_suffix_deletion(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = UUID(await submit_request(harness))
    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        event = await session.scalar(
            select(RequestEvent)
            .where(RequestEvent.request_id == request_id)
            .order_by(RequestEvent.created_at.desc(), RequestEvent.id.desc())
        )
        assert request is not None and event is not None
        original_count = request.audit_event_count
        original_head = request.audit_head_hash
        original_mac = request.audit_anchor_mac
        await session.execute(delete(RequestEvent).where(RequestEvent.id == event.id))
        request.audit_event_count -= 1
        request.audit_head_hash = event.previous_hash
        assert request.audit_event_count == original_count - 1
        assert request.audit_head_hash != original_head
        assert request.audit_anchor_mac == original_mac
        assert not await verify_request_event_integrity(session, request_id)


async def test_audit_integrity_rejects_missing_request(
    api_harness: ApiHarness,
) -> None:
    async with api_harness.sessions() as session:
        assert not await verify_request_event_integrity(session, uuid4())
