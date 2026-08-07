"""Repository idempotency, limits and not-found boundary coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from conftest import ApiHarness
from istari_service.product_errors import ProductConflict, ProductNotFound
from istari_service.product_models import ProductPackage
from istari_service.product_types import ScanDecision, ScanResult
from istari_service.repositories.products import SqlAlchemyProductRepository
from product_test_support import create_product_request, product_actors


async def test_repository_not_found_and_package_idempotency(
    api_harness: ApiHarness,
) -> None:
    requester, other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    other_request_id = await create_product_request(api_harness, other, analyst)
    key = uuid4()
    missing = uuid4()

    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, key)
        repeated = await repository.create_package(request_id, analyst.id, key)
        assert repeated.id == package.id
        with pytest.raises(ProductNotFound):
            await repository.create_package(other_request_id, analyst.id, key)
        assert await repository.package(missing, lock=False) is None
        assert await repository.latest_package(missing) is None
        with pytest.raises(ProductNotFound):
            await repository.view(missing)
        with pytest.raises(ProductNotFound):
            await repository.freeze(missing, "a" * 64)
        with pytest.raises(ProductNotFound):
            await repository.approve(missing, analyst.id, now=datetime.now(UTC))
        with pytest.raises(ProductNotFound):
            await repository.disseminate(
                missing,
                analyst.id,
                requester.id,
                uuid4(),
                now=datetime.now(UTC),
            )
        with pytest.raises(ProductNotFound):
            await repository.withdraw(
                missing, analyst.id, "Synthetic reason", now=datetime.now(UTC)
            )


async def test_repository_artefact_idempotency_limits_and_scan_edges(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    other_request_id = await create_product_request(api_harness, requester, analyst)
    expiry = datetime.now(UTC) + timedelta(minutes=5)

    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        other_package = await repository.create_package(
            other_request_id, analyst.id, uuid4()
        )
        managed_key = uuid4()
        artefact, intent = await repository.create_managed(
            package.id,
            label="Synthetic managed artefact",
            filename="report.pdf",
            media_type="application/pdf",
            size_bytes=10,
            checksum="a" * 64,
            creation_key=managed_key,
            intent_key=managed_key,
            object_key=f"quarantine/{package.id}/managed",
            token_hash="b" * 64,
            expires_at=expiry,
        )
        repeated, repeated_intent = await repository.create_managed(
            package.id,
            label="Ignored retry label",
            filename="report.pdf",
            media_type="application/pdf",
            size_bytes=10,
            checksum="a" * 64,
            creation_key=managed_key,
            intent_key=managed_key,
            object_key="quarantine/ignored",
            token_hash="c" * 64,
            expires_at=expiry,
        )
        assert repeated.id == artefact.id
        assert repeated_intent.id == intent.id
        with pytest.raises(ProductNotFound):
            await repository.create_managed(
                other_package.id,
                label="Cross-package retry",
                filename="report.pdf",
                media_type="application/pdf",
                size_bytes=10,
                checksum="a" * 64,
                creation_key=managed_key,
                intent_key=managed_key,
                object_key="quarantine/ignored",
                token_hash="c" * 64,
                expires_at=expiry,
            )
        assert await repository.upload_intent(package.id, uuid4(), lock=False) is None
        assert await repository.upload_intent(package.id, intent.id, lock=False)
        with pytest.raises(ProductNotFound):
            await repository.mark_uploaded(uuid4(), now=datetime.now(UTC))
        with pytest.raises(ProductNotFound):
            await repository.record_scan(
                uuid4(),
                uuid4(),
                ScanDecision(ScanResult.FAILED, "test", "1", "TEST"),
                "a" * 64,
                None,
            )
        scan_key = uuid4()
        decision = ScanDecision(ScanResult.FAILED, "test", "1", "SYNTHETIC")
        failed = await repository.record_scan(
            artefact.id, scan_key, decision, "a" * 64, None
        )
        repeated_scan = await repository.record_scan(
            artefact.id, scan_key, decision, "a" * 64, None
        )
        assert repeated_scan.id == failed.id

        for position in range(2, 11):
            await repository.create_external(
                package.id,
                label=f"Synthetic link {position}",
                destination=f"https://example.test/{position}",
                domain="example.test",
                expires_at=None,
                creation_key=uuid4(),
            )
        with pytest.raises(ProductConflict):
            await repository.create_external(
                package.id,
                label="Over package limit",
                destination="https://example.test/overflow",
                domain="example.test",
                expires_at=None,
                creation_key=uuid4(),
            )


async def test_repository_external_and_dissemination_idempotency_edges(
    api_harness: ApiHarness,
) -> None:
    requester, other, _manager, analyst, qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    other_request_id = await create_product_request(api_harness, other, analyst)
    key = uuid4()

    async with api_harness.sessions() as session, session.begin():
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        other_package = await repository.create_package(
            other_request_id, analyst.id, uuid4()
        )
        artefact = await repository.create_external(
            package.id,
            label="Synthetic link",
            destination="https://example.test/item",
            domain="example.test",
            expires_at=None,
            creation_key=key,
        )
        repeated = await repository.create_external(
            package.id,
            label="Ignored retry",
            destination="https://example.test/ignored",
            domain="example.test",
            expires_at=None,
            creation_key=key,
        )
        assert repeated.id == artefact.id
        with pytest.raises(ProductNotFound):
            await repository.create_external(
                other_package.id,
                label="Cross-package retry",
                destination="https://example.test/ignored",
                domain="example.test",
                expires_at=None,
                creation_key=key,
            )

        row = await session.get(ProductPackage, package.id)
        assert row is not None
        row.package_checksum = "d" * 64
        dissemination_key = uuid4()
        await repository.disseminate(
            package.id,
            qc.id,
            requester.id,
            dissemination_key,
            now=datetime.now(UTC),
        )
        repeated_release = await repository.disseminate(
            package.id,
            qc.id,
            requester.id,
            dissemination_key,
            now=datetime.now(UTC),
        )
        assert repeated_release.id == package.id
        with pytest.raises(ProductNotFound):
            await repository.disseminate(
                package.id,
                qc.id,
                other.id,
                dissemination_key,
                now=datetime.now(UTC),
            )
        assert not await repository.dissemination_matches(
            package.id, requester.id, uuid4()
        )

        await repository.withdraw(
            other_package.id,
            qc.id,
            "No dissemination row exists.",
            now=datetime.now(UTC),
        )
