"""A CRIOC routing decision may carry a message for the receiving command."""

from __future__ import annotations

from api_helpers import perform, submit_request
from conftest import ApiHarness


async def _event_messages(harness: ApiHarness, request_id: str) -> list[str]:
    await harness.login("admin2")
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert detail.status_code == 200, detail.text
    return [item["message"] for item in detail.json()["events"]]


async def test_routing_message_reaches_the_activity_record(
    api_harness: ApiHarness,
) -> None:
    request_id = await submit_request(api_harness)
    await perform(
        api_harness,
        "admin4",
        {
            "action": "progress",
            "priority": "MEDIUM",
            "note": "Customer needs this before the planning conference.",
        },
    )
    messages = await _event_messages(api_harness, request_id)
    assert "Progress: Customer needs this before the planning conference." in messages


async def test_routing_without_a_message_keeps_the_default_label(
    api_harness: ApiHarness,
) -> None:
    request_id = await submit_request(api_harness)
    await perform(api_harness, "admin4", {"action": "progress", "priority": "MEDIUM"})
    messages = await _event_messages(api_harness, request_id)
    assert "Intake review completed." in messages


async def test_routing_message_too_short_to_act_on_is_rejected(
    api_harness: ApiHarness,
) -> None:
    """The API holds the same floor the form applies, so a bypassed form cannot
    record a message the receiving command cannot use."""

    await submit_request(api_harness)
    await api_harness.login("admin4")
    items = await api_harness.client.get("/api/v1/work-items")
    work_id = items.json()["items"][0]["id"]
    await api_harness.client.post(
        f"/api/v1/work-items/{work_id}/claim",
        headers=api_harness.mutation_headers(),
    )
    options = await api_harness.client.get(
        f"/api/v1/work-items/{work_id}/routing-options"
    )
    destination = next(o for o in options.json()["items"] if o["code"] == "JOCK")
    response = await api_harness.client.post(
        f"/api/v1/work-items/{work_id}/complete",
        json={
            "action": "progress",
            "priority": "MEDIUM",
            "destinationUnitId": destination["id"],
            "note": "ok",
        },
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 422
