"""Explicit Customer acceptance and route-monitoring classification."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from conftest import ApiHarness
from istari_service.models import RequestStatus, ServiceRequest
from istari_service.product_errors import ProductNotFound
from istari_service.product_models import ProductDissemination, ProductPackage
from istari_service.product_types import PackageStatus
from istari_service.repositories.products import SqlAlchemyProductRepository
from istari_service.request_event_models import RequestEvent
from product_test_support import (
    create_product_request,
    product_actors,
)


async def test_customer_acceptance_is_exact_idempotent_and_visible_to_route(
    api_harness: ApiHarness,
) -> None:
    requester, other_customer, _manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    package_id = uuid4()
    now = datetime.now(UTC)
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.COMPLETED
        request.current_owner = "Customer"
        session.add(
            ProductPackage(
                id=package_id,
                request_id=request_id,
                package_version=1,
                creation_key=uuid4(),
                author_user_id=analyst.id,
                status=PackageStatus.DISSEMINATED,
                package_checksum="a" * 64,
                disseminated_by_user_id=qc.id,
                disseminated_at=now,
                version=1,
            )
        )
        session.add(
            ProductDissemination(
                package_id=package_id,
                recipient_user_id=requester.id,
                disseminated_by_user_id=qc.id,
                idempotency_key=uuid4(),
                package_checksum="a" * 64,
            )
        )

    await api_harness.login("admin4")
    before = (await api_harness.client.get("/api/v1/tracked-requests")).json()
    tracked = next(item for item in before["items"] if item["id"] == str(request_id))
    assert tracked["customerAcceptanceRequired"] is True
    assert tracked["customerAcceptedAt"] is None

    await api_harness.login(other_customer.username)
    denied = await api_harness.client.post(
        f"/api/v1/releases/requests/{request_id}/accept",
        json={"idempotencyKey": str(uuid4())},
        headers=api_harness.mutation_headers(),
    )
    assert denied.status_code == 404

    await api_harness.login(analyst.username)
    staff_denied = await api_harness.client.post(
        f"/api/v1/releases/requests/{request_id}/accept",
        json={"idempotencyKey": str(uuid4())},
        headers=api_harness.mutation_headers(),
    )
    assert staff_denied.status_code == 404

    await api_harness.login(requester.username)
    acceptance_key = str(uuid4())
    accepted = await api_harness.client.post(
        f"/api/v1/releases/requests/{request_id}/accept",
        json={"idempotencyKey": acceptance_key},
        headers=api_harness.mutation_headers(),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["acceptedAt"] is not None
    repeated = await api_harness.client.post(
        f"/api/v1/releases/requests/{request_id}/accept",
        json={"idempotencyKey": acceptance_key},
        headers=api_harness.mutation_headers(),
    )
    assert repeated.status_code == 200
    assert repeated.json()["acceptedAt"] == accepted.json()["acceptedAt"]
    conflict = await api_harness.client.post(
        f"/api/v1/releases/requests/{request_id}/accept",
        json={"idempotencyKey": str(uuid4())},
        headers=api_harness.mutation_headers(),
    )
    assert conflict.status_code == 409

    await api_harness.login("admin4")
    after = (await api_harness.client.get("/api/v1/tracked-requests")).json()
    tracked = next(item for item in after["items"] if item["id"] == str(request_id))
    assert tracked["customerAcceptedAt"] == accepted.json()["acceptedAt"]
    async with api_harness.sessions() as session:
        event_count = await session.scalar(
            select(func.count())
            .select_from(RequestEvent)
            .where(
                RequestEvent.request_id == request_id,
                RequestEvent.type == "PRODUCT_ACCEPTED",
            )
        )
        dissemination = await session.scalar(
            select(ProductDissemination).where(
                ProductDissemination.package_id == package_id
            )
        )
    assert event_count == 1
    assert dissemination is not None
    assert dissemination.accepted_at is not None

    second_package_id = uuid4()
    async with api_harness.sessions() as session, session.begin():
        session.add(
            ProductPackage(
                id=second_package_id,
                request_id=request_id,
                package_version=2,
                creation_key=uuid4(),
                author_user_id=analyst.id,
                status=PackageStatus.DISSEMINATED,
                package_checksum="b" * 64,
                disseminated_by_user_id=qc.id,
                disseminated_at=now,
                version=1,
            )
        )
        session.add(
            ProductDissemination(
                package_id=second_package_id,
                recipient_user_id=requester.id,
                disseminated_by_user_id=qc.id,
                idempotency_key=uuid4(),
                package_checksum="b" * 64,
            )
        )
        await session.flush()
        repository = SqlAlchemyProductRepository(session)
        with pytest.raises(ProductNotFound):
            await repository.accept(
                second_package_id, requester.id, UUID(acceptance_key), now=now
            )
        with pytest.raises(ProductNotFound):
            await repository.accept(uuid4(), requester.id, uuid4(), now=now)
