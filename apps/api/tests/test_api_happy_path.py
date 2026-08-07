"""End-to-end representative workflow through the public FastAPI contract."""

from __future__ import annotations

from typing import Any

from conftest import ApiHarness, request_payload


async def _claim_current(harness: ApiHarness) -> dict[str, Any]:
    response = await harness.client.get("/api/v1/work-items")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    item = items[0]
    if item["assigneeId"] is None:
        claimed = await harness.client.post(
            f"/api/v1/work-items/{item['id']}/claim",
            headers=harness.mutation_headers(),
        )
        assert claimed.status_code == 200, claimed.text
        item = claimed.json()
    return item


async def _complete(
    harness: ApiHarness, item: dict[str, Any], payload: dict[str, Any]
) -> None:
    code_by_action = {
        "progress": "DIGOC",
        "send_to_allocation": "NCGI_A_OPS",
        "allocate": "OSG_TEAM",
    }
    code = code_by_action.get(str(payload.get("action")))
    if code is not None:
        options = await harness.client.get(
            f"/api/v1/work-items/{item['id']}/routing-options"
        )
        destination = next(
            option for option in options.json()["items"] if option["code"] == code
        )
        payload = {**payload, "destinationUnitId": destination["id"]}
    response = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/complete",
        json=payload,
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text


async def test_complete_representative_workflow_and_feedback(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    session = await harness.login("admin2")
    assert session["user"]["role"] == "REQUESTER"
    me = await harness.client.get("/api/v1/auth/me")
    assert me.status_code == 200
    harness.csrf_token = me.json()["csrfToken"]

    created = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["status"] == "ROUTING_PENDING"
    assert await harness.dispatch_start()

    listed = await harness.client.get("/api/v1/requests")
    assert [item["id"] for item in listed.json()["items"]] == [request_id]
    unavailable_product = await harness.client.get(
        f"/api/v1/requests/{request_id}/product"
    )
    assert unavailable_product.status_code == 404

    await harness.login("admin3")
    hidden = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert hidden.status_code == 404

    await harness.login("admin4")
    item = await _claim_current(harness)
    assert item["stage"] == "TRIAGE_REVIEW"
    await _complete(
        harness,
        item,
        {"action": "progress", "category": "Research support", "priority": "HIGH"},
    )

    await harness.login("admin5")
    await _complete(
        harness,
        await _claim_current(harness),
        {"action": "send_to_allocation", "note": "Ready for allocation."},
    )

    await harness.login("admin6")
    await _complete(
        harness,
        await _claim_current(harness),
        {
            "action": "allocate",
            "requiredCapabilities": ["Structured writing"],
        },
    )

    specialist_id = await harness.user_id("admin11")
    lead_session = await harness.login("admin8")
    assert lead_session["user"]["scope"] == "OSG Team"
    assert "OSG_TEAM" not in str(lead_session)
    await _complete(
        harness,
        await _claim_current(harness),
        {"action": "assign", "specialistId": str(specialist_id)},
    )

    specialist_session = await harness.login("admin11")
    assert specialist_session["user"]["scope"] == "OSG Team"
    assert "OSG_TEAM" not in str(specialist_session)
    item = await _claim_current(harness)
    assert item["assigneeId"] == str(specialist_id)
    await _complete(
        harness,
        item,
        {
            "action": "submit",
            "deliverableTitle": "Synthetic service summary",
            "deliverableText": (
                "This is a complete fictional deliverable prepared for testing."
            ),
        },
    )

    await harness.login("admin8")
    await _complete(
        harness,
        await _claim_current(harness),
        {"action": "approve"},
    )

    await harness.login("admin15")
    await _complete(
        harness,
        await _claim_current(harness),
        {"action": "approve"},
    )
    await _complete(
        harness,
        await _claim_current(harness),
        {"action": "release", "recipients": ["Fictional service owner"]},
    )

    await harness.login("admin2")
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "COMPLETED"
    assert detail.json()["deliverable"]["title"] == "Synthetic service summary"
    assert detail.json()["assignedDeliveryTeam"] == "OSG Team"
    assert "OSG_TEAM" not in detail.text

    await harness.login("admin3")
    assert (
        await harness.client.get(f"/api/v1/requests/{request_id}/product")
    ).status_code == 404
    await harness.login("admin4")
    assert (
        await harness.client.get(f"/api/v1/requests/{request_id}/product")
    ).status_code == 404
    await harness.login("admin1")
    assert (
        await harness.client.get(f"/api/v1/requests/{request_id}/product")
    ).status_code == 404
    harness.client.cookies.clear()
    assert (
        await harness.client.get(f"/api/v1/requests/{request_id}/product")
    ).status_code == 401

    await harness.login("admin2")
    product = await harness.client.get(f"/api/v1/requests/{request_id}/product")
    assert product.status_code == 200
    assert (
        product.text == "This is a complete fictional deliverable prepared for testing."
    )
    assert product.headers["content-type"] == "text/plain; charset=utf-8"
    assert product.headers["content-disposition"] == (
        f'attachment; filename="{detail.json()["reference"]}-service-product.txt"'
    )
    assert product.headers["cache-control"] == "no-store"
    assert product.headers["x-content-type-options"] == "nosniff"

    feedback = await harness.client.post(
        f"/api/v1/requests/{request_id}/feedback",
        json={"rating": 5, "comments": "Clear and useful."},
        headers=harness.mutation_headers(),
    )
    assert feedback.status_code == 200
    duplicate = await harness.client.post(
        f"/api/v1/requests/{request_id}/feedback",
        json={"rating": 4, "comments": "A second response."},
        headers=harness.mutation_headers(),
    )
    assert duplicate.status_code == 409
    summary = (await harness.client.get("/api/v1/requests")).json()["items"][0]
    assert summary["productAvailable"] is True
    assert summary["feedbackSubmitted"] is True
