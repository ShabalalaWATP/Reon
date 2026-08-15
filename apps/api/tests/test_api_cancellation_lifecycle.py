"""Cancellation at later human-led workflow stages."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from api_helpers import perform, reach_delivery_work, reach_quality_review
from conftest import ApiHarness
from mist_service.action_notification_models import NotificationEvent
from mist_service.clarification_models import (
    ClarificationStatus,
    ClarificationThread,
)


async def test_quality_stage_cancellation_notifies_the_complete_selected_route(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = UUID(await reach_quality_review(harness))
    await harness.login("admin2")
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    response = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={
            "expectedVersion": detail.json()["version"],
            "reason": "The completed draft is no longer required.",
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200
    async with harness.sessions() as session:
        notification = await session.scalar(
            select(NotificationEvent).where(
                NotificationEvent.request_id == request_id,
                NotificationEvent.event_type == "REQUEST_CANCELLED",
            )
        )
        assert notification is not None
        recipient_ids = {rule["userId"] for rule in notification.audience}
    for username in (
        "admin2",
        "admin4",
        "admin5",
        "admin6",
        "admin8",
        "admin11",
        "admin15",
    ):
        assert str(await harness.user_id(username)) in recipient_ids


async def test_cancellation_withdraws_an_open_customer_clarification(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = UUID(await reach_delivery_work(harness))
    await perform(
        harness,
        "admin11",
        {
            "action": "request_clarification",
            "question": "Which fictional region should be prioritised?",
            "reason": "The scope is required to complete the product accurately.",
            "responseDeadline": (
                datetime.now(UTC).date() + timedelta(days=5)
            ).isoformat(),
        },
    )
    await harness.login("admin2")
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    cancelled = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={
            "expectedVersion": detail.json()["version"],
            "reason": "The fictional requirement has been withdrawn.",
        },
        headers=harness.mutation_headers(),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["clarifications"][0]["status"] == "WITHDRAWN"
    assert cancelled.json()["clarifications"][0]["messages"][-1]["kind"] == (
        "WITHDRAWAL"
    )
    async with harness.sessions() as session:
        thread = await session.scalar(
            select(ClarificationThread).where(
                ClarificationThread.request_id == request_id
            )
        )
        assert thread is not None
        assert thread.status is ClarificationStatus.WITHDRAWN
