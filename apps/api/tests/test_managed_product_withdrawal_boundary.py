"""Managed withdrawal is authoritative over parallel legacy deliverables."""

from dataclasses import replace
from datetime import UTC, datetime

from conftest import ApiHarness
from mist_service.models import (
    Deliverable,
    DeliverableStatus,
    RequestStatus,
)
from mist_service.product_runtime import ProductRuntime
from mist_service.product_security import AllowedHttpsLinkPolicy
from product_test_support import create_product_request, product_actors
from test_api_managed_products import (
    _approve_and_release,
    _command,
    _create_package,
    _set_status,
)


async def test_withdrawal_revokes_dashboard_and_legacy_fallback_access(
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
            label="Synthetic managed product",
            url="https://products.example.test/withdrawal-boundary",
        ),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    response = await api_harness.client.post(
        f"/api/v1/product-packages/{package['id']}/submit",
        json=_command(2, coveringNote="Synthetic product covering note."),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    package = await _approve_and_release(
        api_harness,
        request_id,
        response.json(),
        approved_version=3,
        release_version=4,
        external_link_attested=True,
    )
    await _set_status(api_harness, request_id, RequestStatus.COMPLETED)
    async with api_harness.sessions() as session, session.begin():
        session.add(
            Deliverable(
                request_id=request_id,
                version=1,
                title="Legacy parallel product",
                text="This synthetic product must not bypass managed withdrawal.",
                author_user_id=analyst.id,
                status=DeliverableStatus.RELEASED,
                released_at=datetime.now(UTC),
            )
        )
    await api_harness.login("admin15")
    response = await api_harness.client.post(
        f"/api/v1/releases/{package['id']}/withdraw",
        json=_command(5, reason="Synthetic withdrawal boundary test."),
        headers=api_harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    await api_harness.login("admin2")
    response = await api_harness.client.get("/api/v1/requests")
    item = next(
        item for item in response.json()["items"] if item["id"] == str(request_id)
    )
    assert item["productAvailable"] is False
    detail = await api_harness.client.get(f"/api/v1/requests/{request_id}")
    assert detail.json()["productAvailable"] is False
    assert (
        await api_harness.client.get(f"/api/v1/requests/{request_id}/product")
    ).status_code == 404
    release = await api_harness.client.get(f"/api/v1/releases/requests/{request_id}")
    assert release.status_code == 200
    assert release.json() is None
