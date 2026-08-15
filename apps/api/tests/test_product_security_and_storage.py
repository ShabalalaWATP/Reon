"""Strict product boundary and private streaming-storage regressions."""

from __future__ import annotations

import asyncio
import hashlib
import io
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.product_clamav import (
    ClamAvInstreamScanner,
    CompositeDocumentScanner,
)
from mist_service.product_errors import ProductValidationFailed
from mist_service.product_filesystem_storage import PrivateFilesystemObjectStorage
from mist_service.product_security import (
    PPTX_MEDIA_TYPE,
    AllowedHttpsLinkPolicy,
    SafeDocumentScanner,
    validate_managed_metadata,
)
from mist_service.product_types import ScanResult

PDF_MEDIA = "application/pdf"
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _chunks(*items: bytes) -> AsyncIterator[bytes]:
    for item in items:
        yield item


def _office(*, main: str, extra: str | None = None, payload: bytes = b"safe") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr(main, payload)
        if extra:
            archive.writestr(extra, b"active")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("filename", "media_type", "size", "checksum"),
    [
        ("../report.pdf", PDF_MEDIA, 10, "a" * 64),
        ("report.pdf", DOCX_MEDIA, 10, "a" * 64),
        ("report.doc", "application/msword", 10, "a" * 64),
        ("report.pdf", PDF_MEDIA, 0, "a" * 64),
        ("report.pdf", PDF_MEDIA, 10, "not-a-checksum"),
        ("bad\nname.pdf", PDF_MEDIA, 10, "a" * 64),
    ],
)
def test_managed_metadata_rejects_unsafe_or_mismatched_values(
    filename: str, media_type: str, size: int, checksum: str
) -> None:
    with pytest.raises(ProductValidationFailed):
        validate_managed_metadata(
            filename=filename,
            media_type=media_type,
            size_bytes=size,
            checksum=checksum,
        )


def test_managed_metadata_normalises_approved_format() -> None:
    assert validate_managed_metadata(
        filename="Synthetic Report.PDF",
        media_type="APPLICATION/PDF",
        size_bytes=10,
        checksum="A" * 64,
    ) == ("Synthetic Report.PDF", PDF_MEDIA)


@pytest.mark.parametrize(
    "url",
    [
        "http://products.example.test/item",
        "https://user@products.example.test/item",
        "https://products.example.test/item#secret",
        "https://products.example.test:8443/item",
        "https://127.0.0.1/item",
        "https://10.0.0.1/item",
        "https://other.example.test/item",
        "https://products.example.test\\@other.example/item",
    ],
)
def test_external_link_policy_fails_closed(url: str) -> None:
    policy = AllowedHttpsLinkPolicy(frozenset({"products.example.test"}))
    with pytest.raises(ProductValidationFailed):
        policy.normalise(url)


def test_external_link_policy_normalises_without_fetching() -> None:
    policy = AllowedHttpsLinkPolicy(frozenset({"Products.Example.Test."}))
    assert policy.normalise("https://PRODUCTS.example.test/path?q=1") == (
        "https://products.example.test/path?q=1",
        "products.example.test",
    )
    with pytest.raises(ProductValidationFailed):
        AllowedHttpsLinkPolicy(frozenset()).normalise(
            "https://products.example.test/path"
        )


@pytest.mark.parametrize(
    ("body", "filename", "media_type", "reason"),
    [
        (b"not-pdf", "report.pdf", PDF_MEDIA, "SIGNATURE_MISMATCH"),
        (b"%PDF-1.7\n/Encrypt", "report.pdf", PDF_MEDIA, "ENCRYPTED_DOCUMENT"),
        (b"%PDF-1.7\n/JavaScript", "report.pdf", PDF_MEDIA, "ACTIVE_CONTENT"),
        (
            b"%PDF-1.7\nEICAR-STANDARD-ANTIVIRUS-TEST-FILE",
            "report.pdf",
            PDF_MEDIA,
            "MALWARE_DETECTED",
        ),
        (b"broken zip", "report.docx", DOCX_MEDIA, "SIGNATURE_MISMATCH"),
        (
            _office(main="word/document.xml", extra="word/vbaProject.bin"),
            "report.docx",
            DOCX_MEDIA,
            "ACTIVE_CONTENT",
        ),
        (
            _office(main="other.xml"),
            "report.pptx",
            PPTX_MEDIA_TYPE,
            "INVALID_OFFICE_STRUCTURE",
        ),
    ],
)
async def test_scanner_rejects_malicious_or_invalid_content(
    body: bytes, filename: str, media_type: str, reason: str
) -> None:
    checksum = hashlib.sha256(body).hexdigest()
    result = await SafeDocumentScanner().scan(
        _chunks(body[:3], body[3:]),
        filename=filename,
        declared_media_type=media_type,
        expected_size=len(body),
        expected_checksum=checksum,
    )
    assert result.result is ScanResult.FAILED
    assert result.reason_code == reason


@pytest.mark.parametrize(
    ("body", "filename", "media_type"),
    [
        (b"%PDF-1.7\nSynthetic content", "report.pdf", PDF_MEDIA),
        (
            _office(main="word/document.xml"),
            "report.docx",
            DOCX_MEDIA,
        ),
        (
            _office(main="ppt/presentation.xml"),
            "report.pptx",
            PPTX_MEDIA_TYPE,
        ),
    ],
)
async def test_scanner_accepts_clean_formats_in_multiple_chunks(
    body: bytes, filename: str, media_type: str
) -> None:
    checksum = hashlib.sha256(body).hexdigest()
    result = await SafeDocumentScanner().scan(
        _chunks(body[:2], body[2:9], body[9:]),
        filename=filename,
        declared_media_type=media_type,
        expected_size=len(body),
        expected_checksum=checksum,
    )
    assert result.result is ScanResult.CLEAN
    assert result.reason_code is None


async def test_scanner_rejects_stream_checksum_mismatch() -> None:
    body = b"%PDF-1.7\nSynthetic content"
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=len(body),
        expected_checksum="a" * 64,
    )
    assert result.reason_code == "CHECKSUM_MISMATCH"


async def test_in_memory_storage_streams_upload_and_download() -> None:
    storage = InMemoryPrivateObjectStorage()
    expiry = datetime.now(UTC) + timedelta(minutes=5)
    first = await storage.issue_upload("quarantine/package/item", expires_at=expiry)
    assert (
        await storage.issue_upload("quarantine/package/item", expires_at=expiry)
        == first
    )
    stored = await storage.write_quarantine(
        first.object_key, _chunks(b"one", b"", b"two"), maximum_bytes=6
    )
    assert stored.size_bytes == 6
    assert (
        b"".join([chunk async for chunk in storage.stream_quarantine(first.object_key)])
        == b"onetwo"
    )
    await storage.promote(first.object_key, "released/package/item")
    download = await storage.download(
        "released/package/item", filename="report.pdf", media_type=PDF_MEDIA
    )
    assert b"".join([chunk async for chunk in download.chunks]) == b"onetwo"


async def test_storage_enforces_limit_and_filesystem_containment(tmp_path) -> None:
    memory = InMemoryPrivateObjectStorage()
    with pytest.raises(ProductValidationFailed):
        await memory.write_quarantine(
            "quarantine/item", _chunks(b"123", b"456"), maximum_bytes=5
        )

    storage = PrivateFilesystemObjectStorage(tmp_path / "private-products")
    expiry = datetime.now(UTC) + timedelta(minutes=5)
    with pytest.raises(ProductValidationFailed):
        await storage.issue_upload("../escape", expires_at=expiry)
    grant = await storage.issue_upload("quarantine/package/item", expires_at=expiry)
    stored = await storage.write_quarantine(
        grant.object_key, _chunks(b"abc", b"def"), maximum_bytes=6
    )
    assert stored.checksum == hashlib.sha256(b"abcdef").hexdigest()
    assert await storage.read_quarantine(grant.object_key) == stored
    await storage.promote(grant.object_key, "released/package/item")
    download = await storage.download(
        "released/package/item", filename="report.pdf", media_type=PDF_MEDIA
    )
    assert b"".join([chunk async for chunk in download.chunks]) == b"abcdef"


async def _clam_server(
    response: bytes, *, delay: float = 0
) -> tuple[asyncio.Server, int]:
    async def handler(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        await reader.readuntil(b"\0")
        while True:
            length = int.from_bytes(await reader.readexactly(4), "big")
            if length == 0:
                break
            await reader.readexactly(length)
        if delay:
            await asyncio.sleep(delay)
        writer.write(response + b"\0")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


@pytest.mark.parametrize(
    ("response", "expected", "reason"),
    [
        (b"stream: OK", ScanResult.CLEAN, None),
        (b"stream: Synthetic-Test FOUND", ScanResult.FAILED, "MALWARE_DETECTED"),
        (b"stream: ERROR", ScanResult.UNKNOWN, "SCANNER_RESPONSE_INVALID"),
        (b"x" * 5_000, ScanResult.UNKNOWN, "SCANNER_RESPONSE_INVALID"),
    ],
)
async def test_clamav_instream_response_matrix(
    response: bytes, expected: ScanResult, reason: str | None
) -> None:
    body = b"%PDF-1.7\nSynthetic content"
    server, port = await _clam_server(response)
    async with server:
        result = await ClamAvInstreamScanner(
            "127.0.0.1", port=port, timeout_seconds=1
        ).scan(
            _chunks(body[:4], body[4:]),
            filename="report.pdf",
            declared_media_type=PDF_MEDIA,
            expected_size=len(body),
            expected_checksum=hashlib.sha256(body).hexdigest(),
        )
    assert result.result is expected
    assert result.reason_code == reason


async def test_clamav_timeout_and_unavailable_fail_closed() -> None:
    body = b"%PDF-1.7\nSynthetic content"
    server, port = await _clam_server(b"stream: OK", delay=0.1)
    async with server:
        timed_out = await ClamAvInstreamScanner(
            "127.0.0.1", port=port, timeout_seconds=0.01
        ).scan(
            _chunks(body),
            filename="report.pdf",
            declared_media_type=PDF_MEDIA,
            expected_size=len(body),
            expected_checksum=hashlib.sha256(body).hexdigest(),
        )
    assert timed_out.result is ScanResult.TIMED_OUT
    closed = await asyncio.start_server(lambda _reader, _writer: None, "127.0.0.1", 0)
    closed_port = closed.sockets[0].getsockname()[1]
    closed.close()
    await closed.wait_closed()
    unavailable = await ClamAvInstreamScanner(
        "127.0.0.1", port=closed_port, timeout_seconds=0.05
    ).scan(
        _chunks(body),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert unavailable.result in {ScanResult.UNKNOWN, ScanResult.TIMED_OUT}


async def test_composite_requires_structure_and_malware_clean_results() -> None:
    body = b"%PDF-1.7\nSynthetic content"
    server, port = await _clam_server(b"stream: OK")
    composite = CompositeDocumentScanner(
        SafeDocumentScanner(),
        ClamAvInstreamScanner("127.0.0.1", port=port, timeout_seconds=1),
    )
    async with server:
        clean = await composite.scan(
            _chunks(body[:5], body[5:]),
            filename="report.pdf",
            declared_media_type=PDF_MEDIA,
            expected_size=len(body),
            expected_checksum=hashlib.sha256(body).hexdigest(),
        )
    assert clean.result is ScanResult.CLEAN
    invalid = await composite.scan(
        _chunks(b"not-a-pdf"),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=9,
        expected_checksum=hashlib.sha256(b"not-a-pdf").hexdigest(),
    )
    assert invalid.reason_code == "SIGNATURE_MISMATCH"
