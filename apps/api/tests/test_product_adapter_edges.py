"""Boundary branches for private storage and document scanning adapters."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import istari_service.product_clamav as clamav_module
import istari_service.product_security as security_module
from in_memory_product_storage import InMemoryPrivateObjectStorage
from istari_service.product_clamav import (
    ClamAvInstreamScanner,
    CompositeDocumentScanner,
)
from istari_service.product_errors import (
    ProductDependencyUnavailable,
    ProductValidationFailed,
)
from istari_service.product_filesystem_storage import PrivateFilesystemObjectStorage
from istari_service.product_ports import ScannerAssurance
from istari_service.product_runtime import clamav_product_runtime, local_product_runtime
from istari_service.product_security import (
    AllowedHttpsLinkPolicy,
    SafeDocumentScanner,
)
from istari_service.product_types import ScanResult
from product_test_support import PDF_MEDIA, chunks


@pytest.mark.parametrize(
    "settings",
    [
        ("", 3310, 1.0),
        ("localhost", 0, 1.0),
        ("localhost", 3310, 0.0),
    ],
)
def test_clamav_rejects_invalid_connection_settings(
    settings: tuple[str, int, float],
) -> None:
    with pytest.raises(ValueError):
        ClamAvInstreamScanner(
            settings[0], port=settings[1], timeout_seconds=settings[2]
        )


async def _clam_server(response: bytes) -> tuple[asyncio.Server, int]:
    async def handler(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        await reader.readuntil(b"\0")
        while length := int.from_bytes(await reader.readexactly(4), "big"):
            await reader.readexactly(length)
        writer.write(response + b"\0")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


async def test_clamav_ignores_empty_chunks_and_rejects_size_or_digest() -> None:
    body = b"safe"
    server, port = await _clam_server(b"stream: OK")
    async with server:
        size = await ClamAvInstreamScanner(
            "127.0.0.1", port=port, maximum_bytes=3
        ).scan(
            chunks(b"", body),
            filename="report.pdf",
            declared_media_type=PDF_MEDIA,
            expected_size=len(body),
            expected_checksum=hashlib.sha256(body).hexdigest(),
        )
    assert size.reason_code == "SIZE_MISMATCH"

    server, port = await _clam_server(b"stream: OK")
    async with server:
        digest = await ClamAvInstreamScanner("127.0.0.1", port=port).scan(
            chunks(b"", body),
            filename="report.pdf",
            declared_media_type=PDF_MEDIA,
            expected_size=len(body),
            expected_checksum="a" * 64,
        )
    assert digest.reason_code == "CHECKSUM_MISMATCH"


async def test_composite_rejects_long_and_short_streams_before_scanning() -> None:
    scanner = CompositeDocumentScanner(SafeDocumentScanner(), SafeDocumentScanner())
    checksum = hashlib.sha256(b"1234").hexdigest()
    long = await scanner.scan(
        chunks(b"1234"),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=3,
        expected_checksum=checksum,
    )
    short = await scanner.scan(
        chunks(b"12"),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=4,
        expected_checksum=checksum,
    )
    assert long.reason_code == short.reason_code == "SIZE_MISMATCH"


async def test_in_memory_missing_objects_fail_closed_and_delete_is_safe() -> None:
    storage = InMemoryPrivateObjectStorage()
    with pytest.raises(ProductDependencyUnavailable):
        await storage.read_quarantine("quarantine/missing")
    with pytest.raises(ProductDependencyUnavailable):
        storage.stream_quarantine("quarantine/missing")
    with pytest.raises(ProductDependencyUnavailable):
        await storage.promote("quarantine/missing", "released/missing")
    with pytest.raises(ProductDependencyUnavailable):
        await storage.download(
            "released/missing", filename="missing.pdf", media_type=PDF_MEDIA
        )
    await storage.delete_quarantine("quarantine/missing")


async def test_filesystem_empty_chunks_limits_cleanup_and_missing_objects(
    tmp_path,
) -> None:
    root = tmp_path / "private"
    storage = PrivateFilesystemObjectStorage(root)
    expiry = datetime.now(UTC) + timedelta(minutes=5)
    with pytest.raises(ProductValidationFailed):
        await storage.issue_upload("", expires_at=expiry)
    with pytest.raises(ProductValidationFailed):
        await storage.issue_upload("quarantine\\item", expires_at=expiry)

    grant = await storage.issue_upload("quarantine/package/item", expires_at=expiry)
    assert await storage.issue_upload(grant.object_key, expires_at=expiry) == grant
    stored = await storage.write_quarantine(
        grant.object_key, chunks(b"", b"abc"), maximum_bytes=3
    )
    assert stored.size_bytes == 3
    await storage.delete_quarantine(grant.object_key)
    await storage.delete_quarantine(grant.object_key)
    with pytest.raises(ProductDependencyUnavailable):
        await storage.read_quarantine(grant.object_key)
    with pytest.raises(ProductDependencyUnavailable):
        await storage.download(
            "released/missing", filename="missing.pdf", media_type=PDF_MEDIA
        )

    oversize = await storage.issue_upload(
        "quarantine/package/oversize", expires_at=expiry
    )
    with pytest.raises(ProductValidationFailed):
        await storage.write_quarantine(
            oversize.object_key, chunks(b"123", b"4"), maximum_bytes=3
        )
    assert not list((root / "quarantine/package").glob(".upload-*"))


def test_runtime_factories_preserve_limits_and_fail_closed_domains(tmp_path) -> None:
    local = local_product_runtime(
        tmp_path / "local", allowed_external_domains=frozenset({"example.test"})
    )
    assert local.link_policy.normalise("https://example.test/")[1] == "example.test"
    assert local.scanner_assurance is ScannerAssurance.LOCAL_HEURISTIC
    assert local.approved_semantic_cdr is False
    runtime = clamav_product_runtime(
        InMemoryPrivateObjectStorage(),
        AllowedHttpsLinkPolicy(frozenset()),
        clamav_host="127.0.0.1",
        clamav_port=3311,
        clamav_timeout_seconds=2,
        maximum_file_bytes=2_048,
        maximum_package_bytes=4_096,
    )
    assert runtime.clamav_host == "127.0.0.1"
    assert runtime.clamav_port == 3311
    assert runtime.clamav_timeout_seconds == 2
    assert runtime.maximum_file_bytes == 2_048
    assert runtime.maximum_package_bytes == 4_096
    assert runtime.scanner_assurance is ScannerAssurance.LOCAL_HEURISTIC_AND_MALWARE
    assert runtime.approved_semantic_cdr is False


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test:bad/path",
        "https://\udcff.example.test/path",
        "\nhttps://example.test/path",
    ],
)
def test_external_link_policy_rejects_malformed_boundary_values(url: str) -> None:
    with pytest.raises(ProductValidationFailed):
        AllowedHttpsLinkPolicy(frozenset({"example.test"})).normalise(url)


async def test_clamav_os_error_is_reported_as_unavailable(monkeypatch) -> None:
    async def unavailable(*_args, **_kwargs):
        raise OSError("synthetic scanner outage")

    monkeypatch.setattr(clamav_module.asyncio, "open_connection", unavailable)
    result = await ClamAvInstreamScanner("scanner.test").scan(
        chunks(b"safe"),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=4,
        expected_checksum=hashlib.sha256(b"safe").hexdigest(),
    )
    assert result.result is ScanResult.UNKNOWN
    assert result.reason_code == "SCANNER_UNAVAILABLE"


async def test_local_scanner_rejects_stream_over_its_absolute_limit(
    monkeypatch,
) -> None:
    monkeypatch.setattr(security_module, "MAX_FILE_BYTES", 3)
    monkeypatch.setattr(
        security_module,
        "validate_managed_metadata",
        lambda **_kwargs: ("report.pdf", PDF_MEDIA),
    )
    result = await SafeDocumentScanner().scan(
        chunks(b"1234"),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=4,
        expected_checksum=hashlib.sha256(b"1234").hexdigest(),
    )
    assert result.reason_code == "SIZE_MISMATCH"


class _FakeArchive:
    def __init__(self, entries) -> None:
        self._entries = entries

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def infolist(self):
        return self._entries


def _entry(
    filename: str,
    *,
    flag_bits: int = 0,
    file_size: int = 10,
    compress_size: int = 10,
):
    return SimpleNamespace(
        filename=filename,
        flag_bits=flag_bits,
        file_size=file_size,
        compress_size=compress_size,
    )


@pytest.mark.parametrize(
    ("entries", "reason"),
    [
        ([_entry(f"safe/{index}.xml") for index in range(1_001)], "ARCHIVE_LIMIT"),
        ([_entry("word/document.xml", flag_bits=1)], "ENCRYPTED_DOCUMENT"),
        (
            [
                _entry(
                    "word/document.xml",
                    file_size=security_module.MAX_UNCOMPRESSED_BYTES + 1,
                    compress_size=security_module.MAX_UNCOMPRESSED_BYTES + 1,
                )
            ],
            "ARCHIVE_LIMIT",
        ),
        ([_entry("word/document.xml", file_size=1, compress_size=0)], "ARCHIVE_LIMIT"),
        (
            [_entry("word/document.xml", file_size=20_000, compress_size=1)],
            "ARCHIVE_LIMIT",
        ),
    ],
)
async def test_office_archive_resource_limits_fail_closed(
    monkeypatch, entries, reason: str
) -> None:
    monkeypatch.setattr(
        security_module.zipfile,
        "ZipFile",
        lambda _stream: _FakeArchive(entries),
    )
    body = b"PK\x03\x04synthetic"
    result = await SafeDocumentScanner().scan(
        chunks(body),
        filename="report.docx",
        declared_media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == reason


async def test_office_corrupt_zip_container_is_rejected() -> None:
    body = b"PK\x03\x04not-a-real-archive"
    result = await SafeDocumentScanner().scan(
        chunks(body),
        filename="report.docx",
        declared_media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == "INVALID_CONTAINER"
