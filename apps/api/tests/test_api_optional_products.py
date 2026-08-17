"""Quiet optional-product discovery without weakening object concealment."""

from __future__ import annotations

from uuid import uuid4

from conftest import ApiHarness
from mist_service.models import RequestStatus, ServiceRequest
from product_test_support import create_product_request, product_actors


async def test_accessible_missing_products_return_null_and_others_stay_hidden(
    api_harness: ApiHarness,
) -> None:
    requester, other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)

    await api_harness.login("admin11")
    package = await api_harness.client.get(
        f"/api/v1/product-packages/by-request/{request_id}"
    )
    assert package.status_code == 200
    assert package.json() is None
    unknown_package = await api_harness.client.get(
        f"/api/v1/product-packages/by-request/{uuid4()}"
    )
    assert unknown_package.status_code == 404

    await api_harness.login("admin8")
    manager_package = await api_harness.client.get(
        f"/api/v1/product-packages/by-request/{request_id}"
    )
    assert manager_package.status_code == 200
    assert manager_package.json() is None

    await api_harness.login("admin15")
    premature_qc_package = await api_harness.client.get(
        f"/api/v1/product-packages/by-request/{request_id}"
    )
    assert premature_qc_package.status_code == 404
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.QUALITY_REVIEW
    review_package = await api_harness.client.get(
        f"/api/v1/product-packages/by-request/{request_id}"
    )
    assert review_package.status_code == 200
    assert review_package.json() is None

    await api_harness.login("admin2")
    hidden_package = await api_harness.client.get(
        f"/api/v1/product-packages/by-request/{request_id}"
    )
    assert hidden_package.status_code == 404
    release = await api_harness.client.get(f"/api/v1/releases/requests/{request_id}")
    assert release.status_code == 200
    assert release.json() is None

    await api_harness.login("admin3")
    hidden = await api_harness.client.get(f"/api/v1/releases/requests/{request_id}")
    assert hidden.status_code == 404
    other_request_id = await create_product_request(api_harness, other, analyst)
    own_release = await api_harness.client.get(
        f"/api/v1/releases/requests/{other_request_id}"
    )
    assert own_release.status_code == 200
    assert own_release.json() is None
