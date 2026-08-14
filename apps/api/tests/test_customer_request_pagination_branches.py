"""Customer request keyset pagination branch coverage."""

from __future__ import annotations

from conftest import ApiHarness, request_payload


async def test_customer_request_feed_uses_opaque_next_cursor(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    for title in ("First synthetic request", "Second synthetic request"):
        created = await harness.client.post(
            "/api/v1/requests",
            json={**request_payload(), "title": title},
            headers=harness.mutation_headers(),
        )
        assert created.status_code == 201

    first = await harness.client.get("/api/v1/requests", params={"limit": 1})
    assert first.status_code == 200
    cursor = first.json()["nextCursor"]
    assert cursor
    second = await harness.client.get(
        "/api/v1/requests",
        params={"limit": 1, "cursor": cursor},
    )
    assert second.status_code == 200
    assert second.json()["items"][0]["id"] != first.json()["items"][0]["id"]
