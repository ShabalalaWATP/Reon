"""Regressions for durable upload retries and pinned product policy."""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from conftest import ApiHarness
from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.product_errors import ProductConflict, ProductValidationFailed
from mist_service.product_models import ProductAccessEvent
from mist_service.product_security import AllowedHttpsLinkPolicy, SafeDocumentScanner
from mist_service.repositories.products import SqlAlchemyProductRepository
from mist_service.schemas.products import (
    ExternalLinkCreate,
    ManagedArtefactCreate,
    PackageCreate,
)
from mist_service.services.product_service import ProductService
from product_test_support import (
    PDF_MEDIA,
    RecordingAudit,
    chunks,
    create_product_request,
    product_actors,
    product_service_repositories,
)


def _service(
    session,
    storage: InMemoryPrivateObjectStorage,
    domains: frozenset[str] = frozenset({"products.example.test"}),
) -> ProductService:
    return ProductService(
        product_service_repositories(SqlAlchemyProductRepository(session)),
        storage,
        SafeDocumentScanner(),
        AllowedHttpsLinkPolicy(domains),
        RecordingAudit(),
    )


async def test_managed_upload_retry_refreshes_a_usable_grant_after_restart(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    body = b"%PDF-1.7\nSynthetic retry product"
    command = ManagedArtefactCreate(
        expected_version=1,
        label="Synthetic retry product",
        filename="retry.pdf",
        media_type=PDF_MEDIA,
        size_bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        idempotency_key=uuid4(),
    )
    first_storage = InMemoryPrivateObjectStorage()

    async with api_harness.sessions() as session, session.begin():
        service = _service(session, first_storage)
        package = await service.create_package(
            analyst,
            PackageCreate(
                request_id=request_id,
                expected_version=3,
                idempotency_key=uuid4(),
            ),
        )
        first = await service.add_managed(analyst, package.id, command)

    restarted_storage = InMemoryPrivateObjectStorage()
    async with api_harness.sessions() as session, session.begin():
        service = _service(session, restarted_storage)
        retried = await service.add_managed(analyst, package.id, command)
        assert retried.artefact.id == first.artefact.id
        assert retried.upload_intent.id == first.upload_intent.id
        assert retried.upload_intent.upload_token != first.upload_intent.upload_token
        receipt = await service.upload_content(
            analyst,
            package.id,
            retried.upload_intent.id,
            expected_version=2,
            upload_token=retried.upload_intent.upload_token,
            chunks=chunks(body),
        )
        assert receipt.sha256 == command.sha256


async def test_upload_idempotency_key_cannot_change_metadata(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    storage = InMemoryPrivateObjectStorage()
    key = uuid4()
    original = ManagedArtefactCreate(
        expected_version=1,
        label="Original",
        filename="original.pdf",
        media_type=PDF_MEDIA,
        size_bytes=10,
        sha256="a" * 64,
        idempotency_key=key,
    )
    async with api_harness.sessions() as session, session.begin():
        service = _service(session, storage)
        package = await service.create_package(
            analyst,
            PackageCreate(
                request_id=request_id,
                expected_version=3,
                idempotency_key=uuid4(),
            ),
        )
        await service.add_managed(analyst, package.id, original)
        with pytest.raises(ProductConflict):
            await service.add_managed(
                analyst,
                package.id,
                original.model_copy(update={"filename": "different.pdf"}),
            )


async def test_pinned_domains_narrow_the_environment_policy_per_request(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    first_request = await create_product_request(
        api_harness,
        requester,
        analyst,
        approved_link_domains=("first.example.test",),
    )
    second_request = await create_product_request(
        api_harness,
        requester,
        analyst,
        approved_link_domains=("second.example.test",),
    )
    environment = frozenset(
        {"first.example.test", "second.example.test", "environment-only.example.test"}
    )
    storage = InMemoryPrivateObjectStorage()

    async with api_harness.sessions() as session, session.begin():
        service = _service(session, storage, environment)
        first = await service.create_package(
            analyst,
            PackageCreate(
                request_id=first_request,
                expected_version=3,
                idempotency_key=uuid4(),
            ),
        )
        second = await service.create_package(
            analyst,
            PackageCreate(
                request_id=second_request,
                expected_version=3,
                idempotency_key=uuid4(),
            ),
        )
        await service.add_external(
            analyst,
            first.id,
            ExternalLinkCreate(
                expected_version=1,
                label="First pinned product",
                url="https://first.example.test/product",
                idempotency_key=uuid4(),
            ),
        )
        await service.add_external(
            analyst,
            second.id,
            ExternalLinkCreate(
                expected_version=1,
                label="Second pinned product",
                url="https://second.example.test/product",
                idempotency_key=uuid4(),
            ),
        )
        with pytest.raises(ProductValidationFailed):
            await service.add_external(
                analyst,
                first.id,
                ExternalLinkCreate(
                    expected_version=2,
                    label="Environment-only product",
                    url="https://environment-only.example.test/product",
                    idempotency_key=uuid4(),
                ),
            )

    async with api_harness.sessions() as session:
        environment_missing_pin = _service(
            session, storage, frozenset({"first.example.test"})
        )
        with pytest.raises(ProductValidationFailed):
            await environment_missing_pin.add_external(
                analyst,
                second.id,
                ExternalLinkCreate(
                    expected_version=2,
                    label="Pinned but absent from environment",
                    url="https://second.example.test/other",
                    idempotency_key=uuid4(),
                ),
            )


@pytest.mark.parametrize("supplied", ["not-a-uuid", "x" * 500])
async def test_product_audit_uses_bounded_telemetry_correlation_id(
    api_harness: ApiHarness, supplied: str
) -> None:
    await api_harness.login("admin2")
    artefact_id = uuid4()
    response = await api_harness.client.get(
        f"/api/v1/releases/artefacts/{artefact_id}/download",
        headers={"X-Correlation-ID": supplied},
    )
    assert response.status_code == 404
    normalised = response.headers["X-Correlation-ID"]
    UUID(normalised)
    assert normalised != supplied
    requester_id = await api_harness.user_id("admin2")
    async with api_harness.sessions() as session:
        event = await session.scalar(
            select(ProductAccessEvent)
            .where(ProductAccessEvent.actor_user_id == requester_id)
            .order_by(ProductAccessEvent.created_at.desc())
        )
    assert event is not None
    assert event.correlation_id == normalised
    assert len(event.correlation_id) <= 80
