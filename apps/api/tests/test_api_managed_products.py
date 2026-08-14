"""HTTP contracts for managed-product review, release and Customer access."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from conftest import ApiHarness
from istari_service.models import RequestStatus, ServiceRequest
from istari_service.product_runtime import ProductRuntime
from istari_service.product_security import AllowedHttpsLinkPolicy
from product_test_support import create_product_request, product_actors


def _command(version: int, **extra: Any) -> dict[str, Any]:
    return {
        "expectedVersion": version,
        "idempotencyKey": str(uuid4()),
        **extra,
    }


async def _set_status(
    harness: ApiHarness, request_id: UUID, status: RequestStatus
) -> None:
    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = status


async def _create_package(harness: ApiHarness, request_id: UUID) -> dict[str, Any]:
    response = await harness.client.post(
        "/api/v1/product-packages",
        json={
            "requestId": str(request_id),
            "expectedVersion": 3,
            "idempotencyKey": str(uuid4()),
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _approve_and_release(
    harness: ApiHarness,
    request_id: UUID,
    package: dict[str, Any],
    *,
    approved_version: int,
    release_version: int,
    external_link_attested: bool,
) -> dict[str, Any]:
    await _set_status(harness, request_id, RequestStatus.LEAD_REVIEW)
    await harness.login("admin8")
    response = await harness.client.post(
        f"/api/v1/product-packages/{package['id']}/manager-approve",
        json=_command(
            approved_version,
            packageChecksum=package["packageChecksum"],
        ),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text

    await _set_status(harness, request_id, RequestStatus.READY_FOR_RELEASE)
    await harness.login("admin15")
    response = await harness.client.post(
        f"/api/v1/releases/{package['id']}/disseminate",
        json=_command(
            release_version,
            packageChecksum=package["packageChecksum"],
            externalLinkAttested=external_link_attested,
        ),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_managed_file_full_http_release_download_and_withdraw(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    pdf = b"%PDF-1.7\nSynthetic HTTP managed product"

    await api_harness.login("admin11")
    package = await _create_package(api_harness, request_id)
    package_id = package["id"]

    response = await api_harness.client.get(
        f"/api/v1/product-packages/by-request/{request_id}"
    )
    assert response.status_code == 200
    response = await api_harness.client.get(f"/api/v1/product-packages/{package_id}")
    assert response.status_code == 200

    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package_id}/managed-artefacts",
        json=_command(
            1,
            label="Synthetic HTTP PDF",
            filename="http-product.pdf",
            mediaType="application/pdf",
            sizeBytes=len(pdf),
            sha256=hashlib.sha256(pdf).hexdigest(),
        ),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    intent = response.json()["uploadIntent"]
    response = await api_harness.client.put(
        f"/api/v1/product-packages/{package_id}/uploads/{intent['id']}/content",
        params={"expectedVersion": 2},
        content=pdf,
        headers={
            **api_harness.mutation_headers(),
            "X-Upload-Token": intent["uploadToken"],
            "Content-Type": "application/octet-stream",
        },
    )
    assert response.status_code == 200, response.text
    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package_id}/uploads/{intent['id']}/complete",
        json=_command(3),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package_id}/submit",
        json=_command(4),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    submitted = response.json()

    released = await _approve_and_release(
        api_harness,
        request_id,
        submitted,
        approved_version=5,
        release_version=6,
        external_link_attested=False,
    )
    assert released["status"] == "DISSEMINATED"
    await api_harness.login("admin2")
    unavailable = await api_harness.client.get(
        f"/api/v1/releases/requests/{request_id}"
    )
    assert unavailable.status_code == 200
    assert unavailable.json() is None
    await _set_status(api_harness, request_id, RequestStatus.COMPLETED)

    response = await api_harness.client.get("/api/v1/requests")
    dashboard_item = next(
        item for item in response.json()["items"] if item["id"] == str(request_id)
    )
    assert dashboard_item["productAvailable"] is True
    assert dashboard_item["status"] == "COMPLETED"
    response = await api_harness.client.get(f"/api/v1/requests/{request_id}")
    assert response.json()["productAvailable"] is True
    response = await api_harness.client.get(f"/api/v1/releases/requests/{request_id}")
    assert response.status_code == 200, response.text
    artefact_id = response.json()["artefacts"][0]["id"]
    response = await api_harness.client.get(
        f"/api/v1/releases/artefacts/{artefact_id}/download",
        headers={"X-Correlation-ID": "http-download"},
    )
    assert response.status_code == 200
    assert response.content == pdf
    assert response.headers["cache-control"] == "no-store"
    assert "http-product.pdf" in response.headers["content-disposition"]

    await api_harness.login("admin15")
    response = await api_harness.client.post(
        f"/api/v1/releases/{package_id}/withdraw",
        json=_command(7, reason="Synthetic HTTP withdrawal."),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "WITHDRAWN"


async def test_external_link_full_http_redirect_and_headers(
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

    await api_harness.login("admin11")
    package = await _create_package(api_harness, request_id)
    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package['id']}/external-links",
        json=_command(
            1,
            label="Synthetic external product",
            url="https://products.example.test/synthetic-result",
        ),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package['id']}/submit",
        json=_command(2),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text

    await _approve_and_release(
        api_harness,
        request_id,
        response.json(),
        approved_version=3,
        release_version=4,
        external_link_attested=True,
    )
    await _set_status(api_harness, request_id, RequestStatus.COMPLETED)
    await api_harness.login("admin2")
    response = await api_harness.client.get(f"/api/v1/releases/requests/{request_id}")
    artefact_id = response.json()["artefacts"][0]["id"]
    response = await api_harness.client.get(
        f"/api/v1/releases/artefacts/{artefact_id}/open",
        headers={"X-Correlation-ID": "http-redirect"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("https://products.example.test/")
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"


async def test_http_product_failures_are_bounded_and_non_enumerating(
    api_harness: ApiHarness,
) -> None:
    requester, other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    await api_harness.login("admin11")

    response = await api_harness.client.post(
        "/api/v1/product-packages",
        json={
            "requestId": str(request_id),
            "expectedVersion": 99,
            "idempotencyKey": str(uuid4()),
        },
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 409
    response = await api_harness.client.get(
        f"/api/v1/product-packages/by-request/{uuid4()}"
    )
    assert response.status_code == 404
    response = await api_harness.client.get(f"/api/v1/product-packages/{uuid4()}")
    assert response.status_code == 404

    package = await _create_package(api_harness, request_id)
    package_id = package["id"]
    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package_id}/submit",
        json=_command(1),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 409
    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package_id}/external-links",
        json=_command(
            1,
            label="Expired synthetic link",
            url="https://products.example.test/item",
            expiresAt=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        ),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 422
    response = await api_harness.client.put(
        f"/api/v1/product-packages/{package_id}/uploads/{uuid4()}/content",
        params={"expectedVersion": 1},
        content=b"synthetic",
        headers={
            **api_harness.mutation_headers(),
            "X-Upload-Token": "x" * 32,
        },
    )
    assert response.status_code == 404
    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package_id}/uploads/{uuid4()}/complete",
        json=_command(1),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 404

    transport = api_harness.client._transport
    app = transport.app  # type: ignore[attr-defined]
    runtime: ProductRuntime = app.state.product_runtime
    app.state.product_runtime = replace(runtime, maximum_file_bytes=1_024)
    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package_id}/managed-artefacts",
        json=_command(
            1,
            label="Too large for configured runtime",
            filename="large.pdf",
            mediaType="application/pdf",
            sizeBytes=1_025,
            sha256="a" * 64,
        ),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 422

    await _set_status(api_harness, request_id, RequestStatus.LEAD_REVIEW)
    await api_harness.login("admin8")
    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package_id}/manager-approve",
        json=_command(1, packageChecksum="a" * 64),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 404

    await api_harness.login("admin11")
    response = await api_harness.client.get(
        f"/api/v1/releases/artefacts/{uuid4()}/download"
    )
    assert response.status_code == 404
    await api_harness.login("admin3")
    other_request_id = await create_product_request(api_harness, other, analyst)
    response = await api_harness.client.get(
        f"/api/v1/releases/requests/{other_request_id}"
    )
    assert response.status_code == 200
    assert response.json() is None
    response = await api_harness.client.get(f"/api/v1/releases/requests/{request_id}")
    assert response.status_code == 404
