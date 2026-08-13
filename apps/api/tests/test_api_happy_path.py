"""End-to-end representative workflow through the public FastAPI contract."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import uuid4

from conftest import ApiHarness, request_payload
from istari_service.product_runtime import ProductRuntime
from istari_service.product_security import AllowedHttpsLinkPolicy
from product_test_support import set_synthetic_active_link_domains


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
        "progress": "JOCK",
        "send_to_allocation": "ACSA_B_OPS",
        "allocate": "SSG_TEAM",
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
    async with harness.sessions() as database, database.begin():
        await set_synthetic_active_link_domains(database, ("products.example.test",))
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
        {"action": "progress", "priority": "HIGH"},
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
    first_contributor_id = await harness.user_id("admin12")
    second_contributor_id = await harness.user_id("admin13")
    lead_session = await harness.login("admin8")
    assert lead_session["user"]["scope"] == "SSG Team"
    assert "SSG_TEAM" not in str(lead_session)
    await _complete(
        harness,
        await _claim_current(harness),
        {
            "action": "assign",
            "specialistId": str(specialist_id),
            "contributorIds": [
                str(first_contributor_id),
                str(second_contributor_id),
            ],
            "reason": "The Manager selected the Lead and supporting Contributors.",
        },
    )

    contributor_session = await harness.login("admin12")
    assert contributor_session["user"]["role"] == "DELIVERY_SPECIALIST"
    contributor_detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert contributor_detail.status_code == 200
    assert contributor_detail.json()["contributors"] == [
        {
            "id": str(second_contributor_id),
            "displayName": "Ben Doak",
        },
        {
            "id": str(first_contributor_id),
            "displayName": "Nathan Patterson",
        },
    ]

    contributor_work = (await harness.client.get("/api/v1/work-items")).json()[
        "items"
    ]
    assert len(contributor_work) == 1
    assert contributor_work[0]["assigneeId"] == str(specialist_id)
    assert contributor_work[0]["assignedToCurrentUser"] is True
    assert contributor_work[0]["assignmentRole"] == "ANALYST"
    assert contributor_work[0]["availableActions"] == [
        "submit",
        "request_clarification",
    ]
    contributor_actions = (await harness.client.get("/api/v1/me/actions")).json()
    assert contributor_actions["counts"]["needsMyAction"] == 1
    assert contributor_actions["items"][0]["reference"] == created.json()["reference"]
    assert contributor_actions["items"][0]["deepLink"] == (
        f"/delivery/my-work?requestId={request_id}"
    )

    ben_actions = await harness.login("admin13")
    assert ben_actions["user"]["displayName"] == "Ben Doak"
    ben_workspace = (await harness.client.get("/api/v1/me/actions")).json()
    assert ben_workspace["counts"]["needsMyAction"] == 1
    assert ben_workspace["items"][0]["actionAccess"] == "PERSONAL"

    specialist_session = await harness.login("admin11")
    assert specialist_session["user"]["scope"] == "SSG Team"
    assert "SSG_TEAM" not in str(specialist_session)
    lead_item = await _claim_current(harness)
    assert lead_item["assigneeId"] == str(specialist_id)
    assert lead_item["assignedToCurrentUser"] is True
    assert lead_item["assignmentRole"] == "LEAD_ANALYST"

    ben_session = await harness.login("admin13")
    assert ben_session["user"]["displayName"] == "Ben Doak"
    item = await _claim_current(harness)
    assert item["assigneeId"] == str(specialist_id)
    assert item["assignedToCurrentUser"] is True
    assert item["assignmentRole"] == "ANALYST"
    transport = harness.client._transport
    app = transport.app  # type: ignore[attr-defined]
    runtime: ProductRuntime = app.state.product_runtime
    app.state.product_runtime = replace(
        runtime,
        link_policy=AllowedHttpsLinkPolicy(frozenset({"products.example.test"})),
    )
    package_response = await harness.client.post(
        "/api/v1/product-packages",
        json={
            "requestId": request_id,
            "expectedVersion": item["requestVersion"],
            "idempotencyKey": str(uuid4()),
        },
        headers=harness.mutation_headers(),
    )
    assert package_response.status_code == 201, package_response.text
    package = package_response.json()
    link_response = await harness.client.post(
        f"/api/v1/product-packages/{package['id']}/external-links",
        json={
            "expectedVersion": package["version"],
            "idempotencyKey": str(uuid4()),
            "label": "Synthetic service product",
            "url": "https://products.example.test/service-product",
        },
        headers=harness.mutation_headers(),
    )
    assert link_response.status_code == 200, link_response.text
    package_response = await harness.client.post(
        f"/api/v1/product-packages/{package['id']}/submit",
        json={
            "expectedVersion": link_response.json()["version"],
            "idempotencyKey": str(uuid4()),
        },
        headers=harness.mutation_headers(),
    )
    assert package_response.status_code == 200, package_response.text
    package = package_response.json()
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
    approval = await harness.client.post(
        f"/api/v1/product-packages/{package['id']}/manager-approve",
        json={
            "expectedVersion": package["version"],
            "idempotencyKey": str(uuid4()),
            "packageChecksum": package["packageChecksum"],
        },
        headers=harness.mutation_headers(),
    )
    assert approval.status_code == 200, approval.text
    package = approval.json()
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
    dissemination = await harness.client.post(
        f"/api/v1/releases/{package['id']}/disseminate",
        json={
            "expectedVersion": package["version"],
            "idempotencyKey": str(uuid4()),
            "packageChecksum": package["packageChecksum"],
            "externalLinkAttested": True,
        },
        headers=harness.mutation_headers(),
    )
    assert dissemination.status_code == 200, dissemination.text
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
    assert detail.json()["assignedDeliveryTeam"] == "SSG Team"
    assert detail.json()["productAvailable"] is True
    assert "SSG_TEAM" not in detail.text

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
    assert product.status_code == 404
    managed_product = await harness.client.get(
        f"/api/v1/releases/requests/{request_id}"
    )
    assert managed_product.status_code == 200
    assert managed_product.json()["status"] == "DISSEMINATED"
    assert managed_product.json()["artefacts"][0]["destinationDomain"] == (
        "products.example.test"
    )
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
