"""Content-free evidence for authenticated mutation authorisation denials."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select

from api_helpers import current_item, submit_request
from conftest import ApiHarness
from istari_service.compliance_models import SecurityEvent


async def test_request_and_work_denials_record_bounded_evidence(
    api_harness: ApiHarness,
) -> None:
    first_correlation = str(uuid4())
    request_id = await submit_request(api_harness)
    await api_harness.login("admin4")
    work_id = (await current_item(api_harness))["id"]
    await api_harness.login("admin3")

    request_denial = await api_harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={
            "expectedVersion": 1,
            "reason": "Sensitive narrative must never enter security evidence.",
        },
        headers=api_harness.mutation_headers(),
    )
    work_denial = await api_harness.client.post(
        f"/api/v1/work-items/{work_id}/claim",
        headers={
            **api_harness.mutation_headers(),
            "X-Correlation-ID": first_correlation,
        },
    )
    assert request_denial.status_code == work_denial.status_code == 404

    repeated = await asyncio.gather(
        *(
            api_harness.client.post(
                f"/api/v1/work-items/{work_id}/claim",
                headers={
                    **api_harness.mutation_headers(),
                    "X-Correlation-ID": str(uuid4()),
                },
            )
            for index in range(4)
        )
    )
    assert all(response.status_code == 404 for response in repeated)

    async with api_harness.sessions() as session:
        events = list(
            await session.scalars(
                select(SecurityEvent)
                .where(SecurityEvent.event_type == "AUTHORIZATION_DENIAL")
                .order_by(SecurityEvent.created_at.desc())
                .limit(2)
            )
        )
    assert len(events) == 2
    assert {event.reason_code for event in events} == {"NOT_FOUND"}
    assert {event.request_method for event in events} == {"POST"}
    assert {event.route_template for event in events} == {
        "/requests/{request_id}/cancel",
        "/work-items/{work_id}/claim",
    }
    assert all(event.actor_user_id is not None for event in events)
    assert all(event.source_hash is not None for event in events)
    assert all(event.correlation_id is not None for event in events)
    work_event = next(
        event
        for event in events
        if event.route_template == "/work-items/{work_id}/claim"
    )
    assert work_event.correlation_id == first_correlation
    assert work_event.deduplication_key is not None
    assert "Sensitive narrative" not in repr(events)


async def test_anonymous_true_not_found_does_not_record_denial(
    api_harness: ApiHarness,
) -> None:
    before = await _denial_count(api_harness)
    response = await api_harness.client.post(f"/api/v1/work-items/{uuid4()}/claim")
    assert response.status_code in {401, 403}
    assert await _denial_count(api_harness) == before


async def _denial_count(api_harness: ApiHarness) -> int:
    async with api_harness.sessions() as session:
        events = await session.scalars(
            select(SecurityEvent.id).where(
                SecurityEvent.event_type == "AUTHORIZATION_DENIAL"
            )
        )
        return len(list(events))
