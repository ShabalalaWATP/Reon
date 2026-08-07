"""Production clarification behaviour through the public API contract."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from api_helpers import current_item, perform, reach_delivery_work
from conftest import ApiHarness


async def _request_clarification(
    harness: ApiHarness,
    *,
    question: str,
) -> dict[str, object]:
    return await perform(
        harness,
        "admin11",
        {
            "action": "request_clarification",
            "question": question,
            "reason": "The answer is required to complete the product accurately.",
            "responseDeadline": (
                datetime.now(UTC).date() + timedelta(days=5)
            ).isoformat(),
        },
    )


async def test_repeated_clarification_returns_to_same_analyst_and_is_authorised(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    specialist_id = str(await harness.user_id("admin11"))

    opened = await _request_clarification(
        harness,
        question="Which fictional region should the product prioritise?",
    )
    assert opened["status"] == "CUSTOMER_INFORMATION_REQUIRED"

    analyst_detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert analyst_detail.status_code == 200
    thread = analyst_detail.json()["clarifications"][0]
    assert thread["status"] == "OPEN"
    assert thread["assignedSpecialist"]["id"] == specialist_id
    assert thread["messages"][0]["kind"] == "REQUEST"

    await harness.login("admin8")
    manager_detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert manager_detail.status_code == 200
    assert manager_detail.json()["clarifications"][0]["question"] == thread["question"]

    await harness.login("admin1")
    assert (
        await harness.client.get(f"/api/v1/requests/{request_id}")
    ).status_code == 404

    await harness.login("admin4")
    tracked = await harness.client.get("/api/v1/tracked-requests")
    assert tracked.status_code == 200
    assert tracked.json()["items"][0]["status"] == ("CUSTOMER_INFORMATION_REQUIRED")
    assert thread["question"] not in tracked.text
    assert thread["reason"] not in tracked.text

    await harness.login("admin2")
    customer_detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert customer_detail.status_code == 200
    assert customer_detail.json()["needsRequesterInput"] is True
    customer_task = await current_item(harness)
    assert customer_task["stage"] == "CUSTOMER_INFORMATION_REQUIRED"
    assert customer_task["availableActions"] == ["provide_clarification", "withdraw"]

    stale = await harness.client.post(
        f"/api/v1/work-items/{customer_task['id']}/complete",
        json={
            "action": "provide_clarification",
            "threadId": thread["id"],
            "expectedVersion": 99,
            "information": "A deliberately stale synthetic response.",
        },
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409

    answered = await harness.client.post(
        f"/api/v1/work-items/{customer_task['id']}/complete",
        json={
            "action": "provide_clarification",
            "threadId": thread["id"],
            "expectedVersion": thread["version"],
            "information": "Prioritise the fictional northern region.",
        },
        headers=harness.mutation_headers(),
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["status"] == "IN_PROGRESS"

    await harness.login("admin11")
    resumed = await current_item(harness)
    assert resumed["assigneeId"] == specialist_id
    assert resumed["stage"] == "IN_PROGRESS"

    await _request_clarification(
        harness,
        question="Which fictional time period should the product cover?",
    )
    await harness.login("admin2")
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert [item["status"] for item in detail.json()["clarifications"]] == [
        "ANSWERED",
        "OPEN",
    ]
    assert detail.json()["clarifications"][0]["messages"][1]["kind"] == "RESPONSE"


async def test_customer_can_withdraw_while_answering_production_clarification(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    await _request_clarification(
        harness,
        question="Should this fictional request remain active?",
    )

    await harness.login("admin2")
    task = await current_item(harness)
    withdrawn = await harness.client.post(
        f"/api/v1/work-items/{task['id']}/complete",
        json={"action": "withdraw", "reason": "The fictional need has ended."},
        headers=harness.mutation_headers(),
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["status"] == "CANCELLED"
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    thread = detail.json()["clarifications"][0]
    assert thread["status"] == "WITHDRAWN"
    assert thread["messages"][1]["kind"] == "WITHDRAWAL"
