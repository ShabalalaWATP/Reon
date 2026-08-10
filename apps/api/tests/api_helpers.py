"""Concise public-API workflow helpers for behaviour tests."""

from __future__ import annotations

from typing import Any

from conftest import ApiHarness, request_payload


async def submit_request(harness: ApiHarness) -> str:
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201, response.text
    assert await harness.dispatch_start()
    return str(response.json()["id"])


async def current_item(harness: ApiHarness) -> dict[str, Any]:
    response = await harness.client.get("/api/v1/work-items")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1, items
    item = items[0]
    if item["assigneeId"] is None:
        response = await harness.client.post(
            f"/api/v1/work-items/{item['id']}/claim",
            headers=harness.mutation_headers(),
        )
        assert response.status_code == 200, response.text
        item = response.json()
    return item


async def perform(
    harness: ApiHarness,
    username: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if payload.get("action") == "assign" and "reason" not in payload:
        payload = {
            **payload,
            "contributorIds": payload.get("contributorIds", []),
            "reason": "The Manager selected this accountable delivery team.",
        }
    await harness.login(username)
    item = await current_item(harness)
    payload = await _with_routing_destination(harness, item["id"], payload)
    response = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/complete",
        json=payload,
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _with_routing_destination(
    harness: ApiHarness,
    work_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    code_by_action = {
        "progress": "DIGOC",
        "send_to_allocation": "NCGI_A_OPS",
        "allocate": "OSG_TEAM",
    }
    code = code_by_action.get(str(payload.get("action")))
    if code is None or "destinationUnitId" in payload:
        return payload
    response = await harness.client.get(f"/api/v1/work-items/{work_id}/routing-options")
    assert response.status_code == 200, response.text
    destination = next(
        item for item in response.json()["items"] if item["code"] == code
    )
    return {**payload, "destinationUnitId": destination["id"]}


async def reach_coordination(harness: ApiHarness) -> str:
    request_id = await submit_request(harness)
    await perform(
        harness,
        "admin4",
        {"action": "progress", "priority": "MEDIUM"},
    )
    return request_id


async def reach_allocation(harness: ApiHarness) -> str:
    request_id = await reach_coordination(harness)
    await perform(
        harness,
        "admin5",
        {"action": "send_to_allocation", "note": "Route confirmed."},
    )
    return request_id


async def reach_delivery_planning(harness: ApiHarness) -> str:
    request_id = await reach_allocation(harness)
    await perform(
        harness,
        "admin6",
        {
            "action": "allocate",
            "requiredCapabilities": ["Structured writing"],
        },
    )
    return request_id


async def reach_delivery_work(harness: ApiHarness) -> str:
    request_id = await reach_delivery_planning(harness)
    specialist_id = await harness.user_id("admin11")
    await perform(
        harness,
        "admin8",
        {"action": "assign", "specialistId": str(specialist_id)},
    )
    return request_id


async def reach_lead_review(harness: ApiHarness, *, suffix: str = "") -> str:
    request_id = await reach_delivery_work(harness)
    await perform(
        harness,
        "admin11",
        {
            "action": "submit",
            "deliverableTitle": f"Synthetic summary{suffix}",
            "deliverableText": "A sufficiently long fictional deliverable for review.",
        },
    )
    return request_id


async def reach_quality_review(harness: ApiHarness) -> str:
    request_id = await reach_lead_review(harness)
    await perform(harness, "admin8", {"action": "approve"})
    return request_id
