"""Storage-adapter and parser resource-bound regressions."""

from __future__ import annotations

import asyncio
import hashlib
import io
import shutil
import sqlite3
import struct
import zipfile
from collections.abc import AsyncIterator
from contextlib import closing
from datetime import UTC, datetime, timedelta

import pytest

from mist_service.product_errors import ProductValidationFailed
from mist_service.product_filesystem_storage import PrivateFilesystemObjectStorage
from mist_service.product_security import SafeDocumentScanner
from mist_service.product_types import ScanResult
from mist_service.product_zip_preflight import central_directory_preflight

DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MEDIA = "application/pdf"


async def chunks(body: bytes) -> AsyncIterator[bytes]:
    yield body


def office_document() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("word/document.xml", b"<document>safe</document>")
    return buffer.getvalue()


async def test_filesystem_storage_evicts_grants_and_rejects_symlinks(tmp_path) -> None:
    storage = PrivateFilesystemObjectStorage(
        tmp_path / "private-products", maximum_grants=2
    )
    now = datetime.now(UTC)
    expired = await storage.issue_upload(
        "quarantine/package/expired", expires_at=now - timedelta(seconds=1)
    )
    await storage.issue_upload(
        "quarantine/package/one", expires_at=now + timedelta(minutes=1)
    )
    await storage.issue_upload(
        "quarantine/package/two", expires_at=now + timedelta(minutes=2)
    )
    refreshed = await storage.issue_upload(
        "quarantine/package/expired", expires_at=now + timedelta(minutes=3)
    )
    assert refreshed.token != expired.token
    assert len(storage._grants) == 2

    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    malicious = tmp_path / "private-products" / "quarantine" / "malicious"
    try:
        malicious.symlink_to(outside)
    except OSError:
        pytest.skip("This Windows account cannot create symbolic links.")
    with pytest.raises(ProductValidationFailed, match="symlinks"):
        await storage.read_quarantine("quarantine/malicious")
    assert outside.read_bytes() == b"outside"


async def test_office_zip64_sentinel_is_rejected_before_zipfile(monkeypatch) -> None:
    body = bytearray(office_document())
    eocd = body.rfind(b"PK\x05\x06")
    struct.pack_into("<H", body, eocd + 10, 0xFFFF)
    materialised = False
    original = zipfile.ZipFile

    class TrackingZipFile(original):
        def __init__(self, *args, **kwargs):
            nonlocal materialised
            materialised = True
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(zipfile, "ZipFile", TrackingZipFile)
    result = await SafeDocumentScanner().scan(
        chunks(bytes(body)),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == "ARCHIVE_LIMIT"
    assert not materialised


async def test_document_scanner_bounds_concurrent_work() -> None:
    active = 0
    maximum = 0

    class ProbeScanner(SafeDocumentScanner):
        async def _scan(self, *args, **kwargs):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.01)
            active -= 1
            return await super()._scan(*args, **kwargs)

    body = b"%PDF-1.7\nSynthetic content"
    scanner = ProbeScanner(maximum_concurrent_scans=2)
    results = await asyncio.gather(
        *(
            scanner.scan(
                chunks(body),
                filename="report.pdf",
                declared_media_type=PDF_MEDIA,
                expected_size=len(body),
                expected_checksum=hashlib.sha256(body).hexdigest(),
            )
            for _ in range(6)
        )
    )
    assert all(result.result is ScanResult.CLEAN for result in results)
    assert maximum == 2


def test_document_scanner_rejects_an_empty_worker_pool() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        SafeDocumentScanner(maximum_concurrent_scans=0)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda body, eocd: struct.pack_into("<H", body, eocd + 4, 1), "ARCHIVE_LIMIT"),
        (
            lambda body, eocd: struct.pack_into("<L", body, eocd + 12, 4_194_305),
            "ARCHIVE_LIMIT",
        ),
        (
            lambda body, eocd: body.__setitem__(slice(eocd, eocd + 4), b"NOPE"),
            "INVALID_CONTAINER",
        ),
    ],
)
def test_central_directory_preflight_rejects_adversarial_eocd(mutation, reason) -> None:
    body = bytearray(office_document())
    eocd = body.rfind(b"PK\x05\x06")
    mutation(body, eocd)
    assert central_directory_preflight(io.BytesIO(body)) == reason


def test_central_directory_preflight_rejects_entry_metadata() -> None:
    body = bytearray(office_document())
    central = body.find(b"PK\x01\x02")
    struct.pack_into("<L", body, central + 20, 0xFFFFFFFF)
    assert central_directory_preflight(io.BytesIO(body)) == "ARCHIVE_LIMIT"

    malformed = bytearray(office_document())
    central = malformed.find(b"PK\x01\x02")
    malformed[central : central + 4] = b"NOPE"
    assert central_directory_preflight(io.BytesIO(malformed)) == "INVALID_CONTAINER"


async def test_filesystem_storage_validates_configuration_and_missing_delete(
    tmp_path,
) -> None:
    with pytest.raises(ValueError, match="positive"):
        PrivateFilesystemObjectStorage(tmp_path / "bad", maximum_grants=0)
    storage = PrivateFilesystemObjectStorage(tmp_path / "private")
    await storage.delete_quarantine("quarantine/missing")
    await storage.delete_released("released/missing")
    assert storage.quarantine_keys(limit=1) == ()
    with pytest.raises(ValueError, match="positive"):
        storage.quarantine_keys(limit=0)


async def test_filesystem_quarantine_enumeration_stops_at_limit(tmp_path) -> None:
    storage = PrivateFilesystemObjectStorage(tmp_path / "private")
    for index in range(8):
        await storage.write_quarantine(
            f"quarantine/package/{index}", chunks(b"x"), maximum_bytes=1
        )
    keys = storage.quarantine_keys(limit=3)
    assert len(keys) == 3
    assert all(key.startswith("quarantine/package/") for key in keys)


async def test_filesystem_cursor_is_lexical_not_creation_order(tmp_path) -> None:
    storage = PrivateFilesystemObjectStorage(tmp_path / "private")
    for key in ("quarantine/z/referenced", "quarantine/a/orphan"):
        await storage.write_quarantine(key, chunks(b"x"), maximum_bytes=1)
    first = storage.quarantine_keys(limit=1)
    second = storage.quarantine_keys(limit=1, after=first[-1])
    assert first == ("quarantine/a/orphan",)
    assert second == ("quarantine/z/referenced",)


async def test_filesystem_index_bounds_high_cardinality_enumeration(
    tmp_path, monkeypatch
) -> None:
    storage = PrivateFilesystemObjectStorage(tmp_path / "private")
    for index in range(200):
        await storage.write_quarantine(
            f"quarantine/package-{index:04d}/object", chunks(b"x"), maximum_bytes=1
        )

    def forbidden_scandir(*_args, **_kwargs):
        raise AssertionError("enumeration traversed the object directory tree")

    monkeypatch.setattr(
        "mist_service.product_filesystem_storage.os.scandir", forbidden_scandir
    )
    first = storage.quarantine_keys(limit=7)
    second = storage.quarantine_keys(limit=7, after=first[-1])
    assert len(first) == len(second) == 7
    assert first[-1] < second[0]

    await storage.delete_quarantine(first[0])
    parent = tmp_path / "private" / first[0].rsplit("/", 1)[0]
    assert not parent.exists()


def test_filesystem_resumes_bounded_legacy_index_reconciliation(tmp_path) -> None:
    root = tmp_path / "private"
    for index in range(7):
        path = root / "quarantine" / f"legacy-{index}" / "object"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"legacy")

    first_runtime = PrivateFilesystemObjectStorage(root)
    assert first_runtime.quarantine_keys(limit=10) == ()
    assert first_runtime.reconcile_quarantine_index(limit=3) == 3
    first_page = first_runtime.quarantine_keys(limit=10)
    assert len(first_page) == 3

    restarted = PrivateFilesystemObjectStorage(root)
    assert restarted.reconcile_quarantine_index(limit=3) == 3
    assert len(restarted.quarantine_keys(limit=10)) == 6
    assert restarted.reconcile_quarantine_index(limit=3) == 1
    keys = restarted.quarantine_keys(limit=10)
    assert len(keys) == 7
    assert restarted.reconcile_quarantine_index(limit=3) == 0


def test_quarantine_index_recovers_pending_and_rejects_invalid_bounds(tmp_path) -> None:
    root = tmp_path / "private"
    storage = PrivateFilesystemObjectStorage(root)
    index = storage._index
    with pytest.raises(ValueError, match="enumeration limit"):
        index.keys(limit=0, after=None)
    with pytest.raises(ValueError, match="reconciliation limit"):
        index.reconcile(limit=0)

    present = "quarantine/present/object"
    missing = "quarantine/missing/object"
    present_path = root / present
    present_path.parent.mkdir(parents=True)
    present_path.write_bytes(b"synthetic")
    index.prepare(present)
    index.prepare(missing)
    assert index.reconcile(limit=2) == 1
    assert index.keys(limit=10, after=None) == (present,)

    second = "quarantine/second/object"
    second_path = root / second
    second_path.parent.mkdir(parents=True)
    second_path.write_bytes(b"synthetic")
    index.prepare(second)
    assert index.reconcile(limit=1) == 1


def test_quarantine_index_upgrades_legacy_schema_and_skips_seen_roots(tmp_path) -> None:
    root = tmp_path / "private"
    quarantine = root / "quarantine"
    quarantine.mkdir(parents=True)
    database = root / ".quarantine-index.sqlite3"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "CREATE TABLE quarantine_objects (object_key TEXT PRIMARY KEY)"
        )
    storage = PrivateFilesystemObjectStorage(root)
    index = storage._index
    index._stage_one_legacy_root()
    assert index.reconcile(limit=1) == 0


def test_filesystem_index_closes_connections_before_root_delete(tmp_path) -> None:
    root = tmp_path / "disposable"
    storage = PrivateFilesystemObjectStorage(root)
    storage.quarantine_keys(limit=1)
    storage.reconcile_quarantine_index(limit=1)
    del storage
    shutil.rmtree(root)
    assert not root.exists()


async def test_writer_and_reconciler_do_not_move_live_target(tmp_path) -> None:
    root = tmp_path / "private"
    legacy = root / "quarantine" / "legacy" / "object"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy")
    storage = PrivateFilesystemObjectStorage(root)
    key = "quarantine/live/object"
    writer = asyncio.create_task(
        storage.write_quarantine(key, chunks(b"new"), maximum_bytes=3)
    )
    await asyncio.to_thread(storage.reconcile_quarantine_index, limit=2)
    await writer
    assert await storage.read_quarantine(key)
    assert key in storage.quarantine_keys(limit=10)


async def test_reconciliation_recovers_legacy_sibling_of_indexed_object(
    tmp_path,
) -> None:
    root = tmp_path / "private"
    legacy = root / "quarantine" / "package" / "legacy"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy")
    storage = PrivateFilesystemObjectStorage(root)
    indexed = "quarantine/package/indexed"
    await storage.write_quarantine(indexed, chunks(b"new"), maximum_bytes=3)

    assert storage.reconcile_quarantine_index(limit=10) == 1
    keys = storage.quarantine_keys(limit=10)
    assert keys == (indexed, "quarantine/package/legacy")
    assert await storage.read_quarantine("quarantine/package/legacy")
