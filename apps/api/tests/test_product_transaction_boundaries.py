"""Prove storage, scanner and response streams never inherit metadata sessions."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterable, AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncEngine

from conftest import ApiHarness
from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.auth_service import hash_opaque_token
from mist_service.models import User
from mist_service.product_ports import ScannerAssurance
from mist_service.product_runtime import ProductRuntime
from mist_service.product_security import AllowedHttpsLinkPolicy, SafeDocumentScanner
from mist_service.product_types import (
    ArtefactKind,
    ArtefactLifecycle,
    ArtefactRecord,
    DownloadStream,
    ReleaseAccessRecord,
    ScanDecision,
    StoredObject,
    UploadGrant,
)
from mist_service.repositories.auth import SqlAlchemyAuthRepository
from mist_service.repositories.products import SqlAlchemyProductRepository
from mist_service.schemas.products import (
    ManagedArtefactCreate,
    PackageCreate,
    VersionCommand,
)
from mist_service.services.product_customer_release_service import (
    ProductCustomerReleaseService,
)
from mist_service.services.product_download_service import ProductDownloadService
from mist_service.services.product_review_service import ProductReviewService
from mist_service.services.product_transfer_context import ProductTransferContext
from mist_service.services.product_transfer_service import ProductTransferService
from product_test_support import (
    PDF_MEDIA,
    RecordingAudit,
    chunks,
    create_product_request,
    product_actors,
    product_service,
)


class ConnectionTracker:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.active = 0
        event.listen(engine.sync_engine, "checkout", self.checkout)
        event.listen(engine.sync_engine, "checkin", self.checkin)

    def checkout(self, *_values: object) -> None:
        self.active += 1

    def checkin(self, *_values: object) -> None:
        self.active -= 1

    def close(self) -> None:
        event.remove(self.engine.sync_engine, "checkout", self.checkout)
        event.remove(self.engine.sync_engine, "checkin", self.checkin)


class TransactionProbeStorage(InMemoryPrivateObjectStorage):
    def __init__(self, tracker: ConnectionTracker) -> None:
        super().__init__()
        self.tracker = tracker
        self.operations: list[str] = []

    def observe(self, operation: str) -> None:
        assert self.tracker.active == 0, f"{operation} inherited a database connection"
        self.operations.append(operation)

    async def issue_upload(self, object_key: str, *, expires_at: Any) -> UploadGrant:
        self.observe("issue-upload")
        return await super().issue_upload(object_key, expires_at=expires_at)

    async def write_quarantine(
        self,
        object_key: str,
        content: AsyncIterable[bytes],
        *,
        maximum_bytes: int,
    ) -> StoredObject:
        self.observe("write-quarantine")
        return await super().write_quarantine(
            object_key, content, maximum_bytes=maximum_bytes
        )

    def stream_quarantine(self, object_key: str) -> AsyncIterator[bytes]:
        self.observe("stream-quarantine")
        return super().stream_quarantine(object_key)

    async def promote(self, quarantine_key: str, released_key: str) -> None:
        self.observe("promote")
        await super().promote(quarantine_key, released_key)

    async def delete_quarantine(self, object_key: str) -> None:
        self.observe("delete-quarantine")
        await super().delete_quarantine(object_key)

    async def download(
        self, released_key: str, *, filename: str, media_type: str
    ) -> DownloadStream:
        self.observe("download")
        result = await super().download(
            released_key, filename=filename, media_type=media_type
        )

        async def slow_chunks() -> AsyncIterator[bytes]:
            async for chunk in result.chunks:
                await asyncio.sleep(0)
                self.observe("stream-chunk")
                yield chunk

        return DownloadStream(slow_chunks(), result.media_type, result.filename)


class TransactionProbeScanner:
    assurance = ScannerAssurance.LOCAL_HEURISTIC

    def __init__(self, tracker: ConnectionTracker) -> None:
        self.tracker = tracker
        self.delegate = SafeDocumentScanner()

    async def scan(
        self,
        content: AsyncIterable[bytes],
        **parameters: Any,
    ) -> ScanDecision:
        assert self.tracker.active == 0, "scanner inherited a database connection"
        return await self.delegate.scan(content, **parameters)


async def test_product_external_io_and_slow_stream_release_database_connections(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    await api_harness.login("admin11")
    token = api_harness.client.cookies[api_harness.settings.session_cookie_name]
    now = datetime.now(UTC)
    async with api_harness.sessions() as session:
        mutation_session = await SqlAlchemyAuthRepository(session).find_session(
            hash_opaque_token(token),
            now=now,
            idle_cutoff=now - timedelta(minutes=15),
        )
    assert mutation_session is not None
    async with api_harness.sessions() as session:
        engine = session.bind
    assert isinstance(engine, AsyncEngine)
    tracker = ConnectionTracker(engine)
    storage = TransactionProbeStorage(tracker)
    runtime = ProductRuntime(
        storage=storage,
        scanner=TransactionProbeScanner(tracker),
        link_policy=AllowedHttpsLinkPolicy(frozenset()),
    )
    pdf = b"%PDF-1.7\nSynthetic transaction boundary product"
    checksum = hashlib.sha256(pdf).hexdigest()
    try:
        async with api_harness.sessions() as session, session.begin():
            package = await product_service(
                session, storage, RecordingAudit()
            ).create_package(
                analyst,
                PackageCreate(
                    request_id=request_id,
                    expected_version=3,
                    idempotency_key=uuid4(),
                ),
            )

        async def mutation_fence(session: object, record: object) -> bool:
            del record
            return await SqlAlchemyAuthRepository(session).lock_mutation_context(  # type: ignore[arg-type]
                mutation_session.id,
                expected_context_version=mutation_session.context_version,
            )

        transfer = ProductTransferService(
            ProductTransferContext(
                api_harness.sessions,
                runtime,
                mutation_session,
                lambda session: SqlAlchemyProductRepository(session),
                mutation_fence,  # type: ignore[arg-type]
            )
        )
        intent = await transfer.add_managed(
            analyst,
            package.id,
            ManagedArtefactCreate(
                expected_version=1,
                label="Synthetic boundary product",
                filename="boundary.pdf",
                media_type=PDF_MEDIA,
                size_bytes=len(pdf),
                sha256=checksum,
                idempotency_key=uuid4(),
            ),
        )
        await transfer.upload_content(
            analyst,
            package.id,
            intent.upload_intent.id,
            expected_version=2,
            upload_token=intent.upload_intent.upload_token,
            chunks=chunks(pdf),
        )
        scanned = await transfer.complete_upload(
            analyst,
            package.id,
            intent.upload_intent.id,
            VersionCommand(expected_version=3, idempotency_key=uuid4()),
        )
        artefact = scanned.artefacts[0]
        access = ReleaseAccessRecord(
            request_id=request_id,
            package_id=package.id,
            artefact=ArtefactRecord(
                id=artefact.id,
                package_id=package.id,
                kind=ArtefactKind.MANAGED_FILE,
                lifecycle=ArtefactLifecycle.RELEASED,
                filename=artefact.filename,
                media_type=artefact.media_type,
                size_bytes=artefact.size_bytes,
                checksum=artefact.sha256,
                quarantine_key=None,
                released_key=f"released/{package.id}/{artefact.id}",
            ),
        )

        authorisation_connection_seen = False

        async def authorise(
            self: ProductCustomerReleaseService,
            actor: object,
            artefact_id: object,
            correlation_id: object,
        ) -> ReleaseAccessRecord:
            nonlocal authorisation_connection_seen
            del actor, artefact_id, correlation_id
            assert self._repository.session.in_transaction()  # type: ignore[attr-defined]
            user_id = await self._repository.session.scalar(  # type: ignore[attr-defined]
                select(User.id).where(User.id == requester.id)
            )
            assert user_id == requester.id and tracker.active > 0
            authorisation_connection_seen = True
            return access

        monkeypatch.setattr(
            ProductCustomerReleaseService,
            "authorise_download",
            authorise,
        )
        download_service = ProductDownloadService(
            api_harness.sessions,
            lambda session: product_service(session, storage, RecordingAudit()),
        )
        result = await download_service.download(
            requester, artefact.id, "synthetic-correlation"
        )
        assert authorisation_connection_seen
        assert tracker.active == 0
        iterator = result.chunks
        assert await anext(iterator) == pdf
        await iterator.aclose()
        assert tracker.active == 0

        review_authorisation_seen = False

        async def authorise_review(
            self: ProductReviewService,
            actor: object,
            artefact_id: object,
            correlation_id: object,
        ) -> ReleaseAccessRecord:
            nonlocal review_authorisation_seen
            del actor, artefact_id, correlation_id
            assert self._repository.session.in_transaction()  # type: ignore[attr-defined]
            user_id = await self._repository.session.scalar(  # type: ignore[attr-defined]
                select(User.id).where(User.id == analyst.id)
            )
            assert user_id == analyst.id and tracker.active > 0
            review_authorisation_seen = True
            return access

        monkeypatch.setattr(
            ProductReviewService,
            "authorise_review",
            authorise_review,
        )
        review = await download_service.review(analyst, artefact.id, "synthetic-review")
        assert review_authorisation_seen
        assert tracker.active == 0
        review_iterator = review.chunks
        assert await anext(review_iterator) == pdf
        await review_iterator.aclose()
        assert tracker.active == 0
        assert storage.operations == [
            "issue-upload",
            "write-quarantine",
            "stream-quarantine",
            "promote",
            "delete-quarantine",
            "download",
            "stream-chunk",
            "download",
            "stream-chunk",
        ]
    finally:
        tracker.close()
