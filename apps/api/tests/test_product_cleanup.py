"""Durable abandoned-upload and orphan-object reconciliation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.product_cleanup import ProductUploadCleanup
from mist_service.product_models import ProductArtefact, ProductUploadIntent
from mist_service.product_types import ArtefactLifecycle
from mist_service.repositories.products import SqlAlchemyProductRepository
from mist_service.schemas.products import PackageCreate
from product_test_support import (
    RecordingAudit,
    chunks,
    create_product_request,
    product_actors,
    product_service,
)


async def test_cleanup_expires_intent_and_deletes_orphan(api_harness) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    storage = InMemoryPrivateObjectStorage()
    async with api_harness.sessions() as session, session.begin():
        service = product_service(session, storage, RecordingAudit())
        package = await service.create_package(
            analyst,
            PackageCreate(
                request_id=request_id,
                expected_version=3,
                idempotency_key=uuid4(),
            ),
        )
        payload = b"%PDF-1.7\nSynthetic abandoned upload"
        artefact, intent = await SqlAlchemyProductRepository(session).create_managed(
            package.id,
            label="Abandoned",
            filename="abandoned.pdf",
            media_type="application/pdf",
            size_bytes=len(payload),
            checksum=hashlib.sha256(payload).hexdigest(),
            creation_key=uuid4(),
            intent_key=uuid4(),
            object_key=f"quarantine/{package.id}/abandoned",
            token_hash="a" * 64,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    await storage.write_quarantine(
        intent.object_key, chunks(payload), maximum_bytes=len(payload)
    )
    orphan = "quarantine/orphan/unreferenced"
    await storage.write_quarantine(orphan, chunks(b"orphan"), maximum_bytes=6)

    cleanup = ProductUploadCleanup(api_harness.sessions, storage)
    assert await cleanup.reconcile_once()
    assert intent.object_key not in storage.quarantine_keys(limit=10)
    assert orphan not in storage.quarantine_keys(limit=10)
    assert not await cleanup.reconcile_once()
    async with api_harness.sessions() as session:
        row = await session.get(ProductUploadIntent, intent.id)
        stored_artefact = await session.get(ProductArtefact, artefact.id)
        assert row is not None and row.consumed_at is not None
        assert stored_artefact is not None
        assert stored_artefact.lifecycle is ArtefactLifecycle.EXPIRED


async def test_cleanup_validates_batch_and_preserves_active_lease(api_harness) -> None:
    storage = InMemoryPrivateObjectStorage()
    for size in (0, 1_001):
        try:
            ProductUploadCleanup(api_harness.sessions, storage, batch_size=size)
        except ValueError as error:
            assert "between 1 and 1000" in str(error)
        else:
            raise AssertionError("invalid cleanup batch accepted")

    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        service = product_service(session, storage, RecordingAudit())
        package = await service.create_package(
            analyst,
            PackageCreate(
                request_id=request_id,
                expected_version=3,
                idempotency_key=uuid4(),
            ),
        )
        _artefact, intent = await SqlAlchemyProductRepository(session).create_managed(
            package.id,
            label="Leased",
            filename="leased.pdf",
            media_type="application/pdf",
            size_bytes=1,
            checksum=hashlib.sha256(b"x").hexdigest(),
            creation_key=uuid4(),
            intent_key=uuid4(),
            object_key=f"quarantine/{package.id}/leased",
            token_hash="b" * 64,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        row = await session.get(ProductUploadIntent, intent.id)
        assert row is not None
        row.operation_lease_owner = "active"
        row.operation_lease_generation = 1
        row.operation_lease_expires_at = datetime.now(UTC) + timedelta(minutes=1)
    await storage.write_quarantine(intent.object_key, chunks(b"x"), maximum_bytes=1)
    cleanup = ProductUploadCleanup(api_harness.sessions, storage)
    assert not await cleanup.reconcile_once()
    assert intent.object_key in storage.quarantine_keys(limit=10)


async def test_cleanup_bounds_storage_enumeration(api_harness) -> None:
    class TrackingStorage(InMemoryPrivateObjectStorage):
        requested_limits: list[int]

        def __init__(self) -> None:
            super().__init__()
            self.requested_limits = []

        def quarantine_keys(
            self, *, limit: int = 1_000, after: str | None = None
        ) -> tuple[str, ...]:
            self.requested_limits.append(limit)
            return super().quarantine_keys(limit=limit, after=after)

    storage = TrackingStorage()
    for index in range(20):
        await storage.write_quarantine(
            f"quarantine/orphans/{index}", chunks(b"x"), maximum_bytes=1
        )
    report = await ProductUploadCleanup(
        api_harness.sessions, storage, batch_size=3
    ).run()
    assert storage.requested_limits == [3]
    assert report.orphan_objects == 3
    assert len(storage.quarantine_keys(limit=100)) == 17


async def test_cleanup_cursor_reaches_orphan_after_referenced_page(api_harness) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    storage = InMemoryPrivateObjectStorage()
    async with api_harness.sessions() as session, session.begin():
        service = product_service(session, storage, RecordingAudit())
        package = await service.create_package(
            analyst,
            PackageCreate(
                request_id=request_id,
                expected_version=3,
                idempotency_key=uuid4(),
            ),
        )
        for index in range(2):
            await SqlAlchemyProductRepository(session).create_managed(
                package.id,
                label=f"Referenced {index}",
                filename=f"referenced-{index}.pdf",
                media_type="application/pdf",
                size_bytes=1,
                checksum=hashlib.sha256(b"x").hexdigest(),
                creation_key=uuid4(),
                intent_key=uuid4(),
                object_key=f"quarantine/a/{index}",
                token_hash=f"{index + 1:064x}",
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
    for index in range(2):
        await storage.write_quarantine(
            f"quarantine/a/{index}", chunks(b"x"), maximum_bytes=1
        )
    orphan = "quarantine/z/orphan"
    await storage.write_quarantine(orphan, chunks(b"x"), maximum_bytes=1)
    cleanup = ProductUploadCleanup(api_harness.sessions, storage, batch_size=2)
    first = await cleanup.run()
    assert first.orphan_objects == 0 and orphan in storage.quarantine_keys(limit=10)
    second = await cleanup.run()
    assert second.orphan_objects == 1
    assert orphan not in storage.quarantine_keys(limit=10)


async def test_cleanup_preserves_consumed_intent_until_service_deletes_object(
    api_harness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    storage = InMemoryPrivateObjectStorage()
    async with api_harness.sessions() as session, session.begin():
        service = product_service(session, storage, RecordingAudit())
        package = await service.create_package(
            analyst,
            PackageCreate(
                request_id=request_id,
                expected_version=3,
                idempotency_key=uuid4(),
            ),
        )
        _artefact, intent = await SqlAlchemyProductRepository(session).create_managed(
            package.id,
            label="Consumed",
            filename="consumed.pdf",
            media_type="application/pdf",
            size_bytes=1,
            checksum=hashlib.sha256(b"x").hexdigest(),
            creation_key=uuid4(),
            intent_key=uuid4(),
            object_key=f"quarantine/{package.id}/consumed",
            token_hash="c" * 64,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        row = await session.get(ProductUploadIntent, intent.id)
        assert row is not None
        row.consumed_at = datetime.now(UTC)
    await storage.write_quarantine(intent.object_key, chunks(b"x"), maximum_bytes=1)

    report = await ProductUploadCleanup(api_harness.sessions, storage).run()
    assert report.orphan_objects == 0
    assert intent.object_key in storage.quarantine_keys(limit=10)
