"""Public API concealment across roles, assignments and route siblings."""

from __future__ import annotations

from uuid import uuid4

from httpx import Response

from api_helpers import current_item, submit_request
from conftest import ApiHarness


def _assert_same_concealment(actual: Response, unknown: Response) -> None:
    assert actual.status_code == unknown.status_code == 404
    assert (
        actual.json()
        == unknown.json()
        == {
            "detail": {
                "code": "NOT_FOUND",
                "message": "The requested item was not found.",
            }
        }
    )


async def test_request_and_work_identifiers_are_concealed_across_roles(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await submit_request(harness)
    await harness.login("admin4")
    item = await current_item(harness)
    work_id = item["id"]

    for username in ("admin1", "admin3", "admin5", "admin7", "admin11"):
        await harness.login(username)
        forbidden_detail = await harness.client.get(f"/api/v1/requests/{request_id}")
        unknown_detail = await harness.client.get(f"/api/v1/requests/{uuid4()}")
        _assert_same_concealment(forbidden_detail, unknown_detail)

        forbidden_claim = await harness.client.post(
            f"/api/v1/work-items/{work_id}/claim",
            headers=harness.mutation_headers(),
        )
        unknown_claim = await harness.client.post(
            f"/api/v1/work-items/{uuid4()}/claim",
            headers=harness.mutation_headers(),
        )
        _assert_same_concealment(forbidden_claim, unknown_claim)

    await harness.login("admin3")
    cancel = await harness.client.post(
        f"/api/v1/requests/{request_id}/cancel",
        json={"expectedVersion": 1, "reason": "This is not the owning Customer."},
        headers=harness.mutation_headers(),
    )
    feedback = await harness.client.post(
        f"/api/v1/requests/{request_id}/feedback",
        json={"rating": 5, "comments": "Not the owning Customer."},
        headers=harness.mutation_headers(),
    )
    product = await harness.client.get(f"/api/v1/requests/{request_id}/product")
    assert cancel.status_code == feedback.status_code == product.status_code == 404

    await harness.login("admin4")
    owner_detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert owner_detail.status_code == 200
    colleague_completion = await harness.login("admin7")
    assert colleague_completion["user"]["role"] == "INTAKE_TRIAGE"
    denied = await harness.client.post(
        f"/api/v1/work-items/{work_id}/complete",
        json={"action": "close", "reason": "An unassigned colleague cannot act."},
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 404


async def test_sibling_route_user_cannot_discover_direct_work_identifiers(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await submit_request(harness)
    await harness.login("admin4")
    triage = await current_item(harness)
    options = await harness.client.get(
        f"/api/v1/work-items/{triage['id']}/routing-options"
    )
    jock = next(item for item in options.json()["items"] if item["code"] == "JOCK")
    progressed = await harness.client.post(
        f"/api/v1/work-items/{triage['id']}/complete",
        json={
            "action": "progress",
            "priority": "MEDIUM",
            "destinationUnitId": jock["id"],
        },
        headers=harness.mutation_headers(),
    )
    assert progressed.status_code == 200, progressed.text

    await harness.login("admin76")
    jock_item = await current_item(harness)
    await harness.login("admin78")
    assert (await harness.client.get("/api/v1/work-items")).json() == {
        "items": [],
        "nextCursor": None,
    }

    forbidden_detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    unknown_detail = await harness.client.get(f"/api/v1/requests/{uuid4()}")
    _assert_same_concealment(forbidden_detail, unknown_detail)
    forbidden_options = await harness.client.get(
        f"/api/v1/work-items/{jock_item['id']}/routing-options"
    )
    unknown_options = await harness.client.get(
        f"/api/v1/work-items/{uuid4()}/routing-options"
    )
    _assert_same_concealment(forbidden_options, unknown_options)
