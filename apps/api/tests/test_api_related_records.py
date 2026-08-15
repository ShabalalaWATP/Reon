"""Scoped explainable related-request matching through the public API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from conftest import ApiHarness, request_payload
from mist_service.models import Deliverable, DeliverableStatus


async def _submit(harness: ApiHarness, title: str, **updates: Any) -> dict[str, Any]:
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(title=title, **updates),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201, response.text
    assert await harness.dispatch_start()
    return response.json()


async def _claim(
    harness: ApiHarness,
    request_id: str,
    username: str = "admin4",
) -> dict[str, Any]:
    await harness.login(username)
    items = (await harness.client.get("/api/v1/work-items")).json()["items"]
    item = next(row for row in items if row["requestId"] == request_id)
    response = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/claim",
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_intake_search_and_append_only_link_lifecycle(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    candidate = await _submit(harness, "Northern readiness assessment")
    field_match = await _submit(
        harness,
        "A title without the searched phrase",
        supportingInformation="A distinctive orrery-cadence supporting record.",
    )
    source = await _submit(harness, "Southern readiness assessment")
    item = await _claim(harness, source["id"])
    root = f"/api/v1/work-items/{item['id']}"

    workspace = await harness.client.get(f"{root}/request-links")
    assert workspace.status_code == 200
    assert workspace.json()["items"] == []
    version = workspace.json()["sourceVersion"]

    search = await harness.client.get(
        f"{root}/related-records", params={"query": "Northern", "limit": 20}
    )
    assert search.status_code == 200
    assert search.json()["mode"] == "TEXT_ONLY"
    match = search.json()["items"][0]
    assert match["id"] == candidate["id"]
    assert match["reference"] == candidate["reference"]
    assert match["matchStrength"] > 0
    assert match["methods"] == ["FULL_TEXT", "STRUCTURED"]
    assert match["evidence"][0]["field"] == "Title"

    automatic = await harness.client.get(f"{root}/related-records")
    assert automatic.status_code == 200
    assert automatic.json()["items"][0]["id"] == candidate["id"]

    field_search = await harness.client.get(
        f"{root}/related-records", params={"query": "orrery-cadence"}
    )
    assert field_search.status_code == 200
    assert field_search.json()["items"][0]["id"] == field_match["id"]
    assert field_search.json()["items"][0]["evidence"][0]["field"] == (
        "Supporting information"
    )
    literal_wildcard = await harness.client.get(
        f"{root}/related-records", params={"query": "%_"}
    )
    assert literal_wildcard.status_code == 200
    assert literal_wildcard.json()["items"] == []

    created = await harness.client.post(
        f"{root}/request-links",
        headers=harness.mutation_headers(),
        json={
            "expectedVersion": version,
            "targetRequestId": candidate["id"],
            "linkType": "RELATED_REQUEST",
            "reason": "Both requests concern the same fictional readiness period.",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["sourceVersion"] == version + 1
    assert body["items"][0]["actorDisplayName"] == "Scott McTominay"
    assert body["items"][0]["target"]["reference"] == candidate["reference"]

    stale = await harness.client.post(
        f"{root}/request-links",
        headers=harness.mutation_headers(),
        json={
            "expectedVersion": version,
            "targetRequestId": candidate["id"],
            "linkType": "POSSIBLE_DUPLICATE",
            "reason": "A deliberately stale version must never append a link.",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "STALE_VERSION"

    duplicate = await harness.client.post(
        f"{root}/request-links",
        headers=harness.mutation_headers(),
        json={
            "expectedVersion": body["sourceVersion"],
            "targetRequestId": candidate["id"],
            "linkType": "RELATED_REQUEST",
            "reason": "The same typed relationship must not be recorded twice.",
        },
    )
    assert duplicate.status_code == 409

    not_relevant = await harness.client.post(
        f"{root}/request-links",
        headers=harness.mutation_headers(),
        json={
            "expectedVersion": body["sourceVersion"],
            "targetRequestId": field_match["id"],
            "linkType": "NOT_RELEVANT",
            "reason": "The wording matched, but the underlying customer need differs.",
        },
    )
    assert not_relevant.status_code == 200
    assert any(
        item["linkType"] == "NOT_RELEVANT" for item in not_relevant.json()["items"]
    )


async def test_related_record_scope_validation_and_released_output(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    candidate = await _submit(harness, "Published readiness response")
    source = await _submit(harness, "Request needing prior work")
    item = await _claim(harness, source["id"])
    root = f"/api/v1/work-items/{item['id']}"
    version = (await harness.client.get(f"{root}/request-links")).json()[
        "sourceVersion"
    ]

    unavailable = await harness.client.post(
        f"{root}/request-links",
        headers=harness.mutation_headers(),
        json={
            "expectedVersion": version,
            "targetRequestId": candidate["id"],
            "linkType": "EXISTING_OUTPUT",
            "reason": "The candidate does not yet contain a released product.",
        },
    )
    assert unavailable.status_code == 409

    async with harness.sessions() as session:
        session.add(
            Deliverable(
                request_id=UUID(candidate["id"]),
                version=1,
                title="Published synthetic response",
                text="A sufficiently long fictional released service product.",
                author_user_id=await harness.user_id("admin11"),
                status=DeliverableStatus.RELEASED,
                released_by_user_id=await harness.user_id("admin15"),
                released_at=datetime.now(UTC),
            )
        )
        await session.commit()

    search = await harness.client.get(
        f"{root}/related-records", params={"query": "Published"}
    )
    assert search.json()["items"][0]["productAvailable"] is True
    recorded = await harness.client.post(
        f"{root}/request-links",
        headers=harness.mutation_headers(),
        json={
            "expectedVersion": version,
            "targetRequestId": candidate["id"],
            "linkType": "EXISTING_OUTPUT",
            "reason": "The released product may already meet this customer need.",
        },
    )
    assert recorded.status_code == 200, recorded.text

    self_link = await harness.client.post(
        f"{root}/request-links",
        headers=harness.mutation_headers(),
        json={
            "expectedVersion": recorded.json()["sourceVersion"],
            "targetRequestId": source["id"],
            "linkType": "RELATED_REQUEST",
            "reason": "A request cannot be linked to itself under any link type.",
        },
    )
    assert self_link.status_code == 409

    await harness.login("admin7")
    assert (await harness.client.get(f"{root}/request-links")).status_code == 404
    await harness.login("admin5")
    assert (
        await harness.client.get(
            f"{root}/related-records", params={"query": "Published"}
        )
    ).status_code == 404


async def test_related_record_input_bounds(api_harness: ApiHarness) -> None:
    harness = api_harness
    source = await _submit(harness, "Input validation source")
    item = await _claim(harness, source["id"])
    root = f"/api/v1/work-items/{item['id']}"
    assert (
        await harness.client.get(f"{root}/related-records", params={"query": "x"})
    ).status_code == 422
    assert (
        await harness.client.get(f"{root}/related-records", params={"query": "x" * 241})
    ).status_code == 422
    workspace = await harness.client.get(f"{root}/request-links")
    invalid_reason = await harness.client.post(
        f"{root}/request-links",
        headers=harness.mutation_headers(),
        json={
            "expectedVersion": workspace.json()["sourceVersion"],
            "targetRequestId": source["id"],
            "linkType": "RELATED_REQUEST",
            "reason": "          ",
        },
    )
    assert invalid_reason.status_code == 422
