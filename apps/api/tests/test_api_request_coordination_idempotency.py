"""Compatibility coordination endpoint idempotency and disclosure behaviour."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import func, select

from api_helpers import reach_delivery_work
from conftest import ApiHarness
from istari_service.request_event_models import RequestEvent


async def test_coordination_retry_reuses_event_without_revealing_body(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    await harness.login("admin11")
    secret_body = "Synthetic target-only detail must not enter broad history."
    payload = {
        "audience": "CUSTOMER",
        "body": secret_body,
        "clientMutationId": str(uuid4()),
    }
    first = await harness.client.post(
        f"/api/v1/requests/{request_id}/coordination",
        json=payload,
        headers=harness.mutation_headers(),
    )
    repeated = await harness.client.post(
        f"/api/v1/requests/{request_id}/coordination",
        json=payload,
        headers=harness.mutation_headers(),
    )
    assert first.status_code == 200, first.text
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["event"]["id"] == first.json()["event"]["id"]
    assert first.json()["event"]["message"] == "Question for Customer recorded."
    assert secret_body not in first.text
    async with harness.sessions() as session:
        event_count = await session.scalar(
            select(func.count(RequestEvent.id)).where(
                RequestEvent.request_id == UUID(request_id),
                RequestEvent.type == "COORDINATION_MESSAGE",
            )
        )
    assert event_count == 1
