"""HTTP boundaries for pre-release managed-product inspection."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select

from conftest import ApiHarness
from mist_service.product_models import ProductAccessEvent
from mist_service.product_runtime import ProductRuntime
from mist_service.product_security import AllowedHttpsLinkPolicy
from mist_service.product_types import AccessOutcome
from product_test_support import create_product_request, product_actors

pytestmark = pytest.mark.anyio


def _command(version: int, **extra: Any) -> dict[str, Any]:
    return {
        "expectedVersion": version,
        "idempotencyKey": str(uuid4()),
        **extra,
    }


async def _clean_file(
    harness: ApiHarness, request_id: str, content: bytes
) -> tuple[str, str]:
    package_response = await harness.client.post(
        "/api/v1/product-packages",
        json={
            "requestId": request_id,
            "expectedVersion": 3,
            "idempotencyKey": str(uuid4()),
        },
        headers=harness.mutation_headers(),
    )
    package_id = package_response.json()["id"]
    digest = hashlib.sha256(content).hexdigest()
    intent_response = await harness.client.post(
        f"/api/v1/product-packages/{package_id}/managed-artefacts",
        json=_command(
            1,
            label="Synthetic review product",
            filename="review.pdf",
            mediaType="application/pdf",
            sizeBytes=len(content),
            sha256=digest,
        ),
        headers=harness.mutation_headers(),
    )
    assert intent_response.status_code == 200, intent_response.text
    intent = intent_response.json()["uploadIntent"]
    upload_response = await harness.client.put(
        f"/api/v1/product-packages/{package_id}/uploads/{intent['id']}/content",
        params={"expectedVersion": 2},
        content=content,
        headers={
            **harness.mutation_headers(),
            "X-Upload-Token": intent["uploadToken"],
            "Content-Type": "application/pdf",
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    completed = await harness.client.post(
        f"/api/v1/product-packages/{package_id}/uploads/{intent['id']}/complete",
        json=_command(3),
        headers=harness.mutation_headers(),
    )
    assert completed.status_code == 200, completed.text
    return package_id, completed.json()["artefacts"][0]["id"]


async def test_staff_review_is_exact_bounded_and_not_customer_visible(
    api_harness: ApiHarness,
) -> None:
    transport = api_harness.client._transport
    app = transport.app  # type: ignore[attr-defined]
    runtime: ProductRuntime = app.state.product_runtime
    app.state.product_runtime = replace(
        runtime,
        link_policy=AllowedHttpsLinkPolicy(frozenset({"products.example.test"})),
    )
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    content = b"%PDF-1.7\nSynthetic review product"
    await api_harness.login("admin11")
    package_id, artefact_id = await _clean_file(api_harness, str(request_id), content)

    package = await api_harness.client.get(f"/api/v1/product-packages/{package_id}")
    review_url = package.json()["artefacts"][0]["reviewUrl"]
    assert review_url == f"/api/v1/product-packages/artefacts/{artefact_id}/review"
    review = await api_harness.client.get(review_url)
    assert review.status_code == 200
    assert review.content == content
    assert review.headers["cache-control"] == "no-store"
    assert review.headers["x-content-type-options"] == "nosniff"
    assert review.headers["content-disposition"].startswith("inline;")
    destination = "https://products.example.test/review?token=synthetic"
    linked = await api_harness.client.post(
        f"/api/v1/product-packages/{package_id}/external-links",
        json=_command(
            4,
            label="Synthetic linked product",
            url=destination,
        ),
        headers=api_harness.mutation_headers(),
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["artefacts"][1]["reviewDestinationUrl"] == destination

    for username in ("admin4", "admin2"):
        await api_harness.login(username)
        assert (await api_harness.client.get(review_url)).status_code == 404
        assert (
            await api_harness.client.get(f"/api/v1/product-packages/{package_id}")
        ).status_code == 404


async def test_unknown_staff_review_probe_is_audited_without_content_metadata(
    api_harness: ApiHarness,
) -> None:
    await api_harness.login("admin11")
    target = uuid4()
    response = await api_harness.client.get(
        f"/api/v1/product-packages/artefacts/{target}/review"
    )
    assert response.status_code == 404
    async with api_harness.sessions() as session:
        event = await session.scalar(
            select(ProductAccessEvent).where(
                ProductAccessEvent.target_hash
                == hashlib.sha256(str(target).encode("ascii")).hexdigest()
            )
        )
    assert event is not None
    assert event.actor_user_id == await api_harness.user_id("admin11")
    assert event.outcome is AccessOutcome.DENIED
    assert event.reason_code == "STAFF_REVIEW_ACCESS_DENIED"
    assert event.request_id is None
    assert event.package_id is None
    assert event.artefact_id is None
