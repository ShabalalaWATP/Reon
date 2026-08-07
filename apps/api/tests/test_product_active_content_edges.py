"""Adversarial active-content cases for managed product inspection."""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import AsyncIterator

import pytest

from istari_service.product_security import (
    MAX_FILE_BYTES,
    SafeDocumentScanner,
    normalise_product_correlation_id,
)
from istari_service.product_types import ScanResult

PDF_MEDIA = "application/pdf"
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_product_correlation_ids_are_bounded_and_content_minimised() -> None:
    assert normalise_product_correlation_id("   ") is None
    assert (
        normalise_product_correlation_id("safe-correlation_1") == "safe-correlation_1"
    )
    normalised = normalise_product_correlation_id("unsafe value")
    assert normalised is not None and normalised.startswith("sha256:")
    assert len(normalised) == 71
    assert normalised == normalise_product_correlation_id("unsafe value")


def test_pdf_inspector_rejects_content_above_its_internal_bound() -> None:
    body = b"%PDF-" + (b"x" * (MAX_FILE_BYTES - 4))
    assert SafeDocumentScanner._inspect_pdf(io.BytesIO(body)) == "ARCHIVE_LIMIT"


async def _chunks(body: bytes) -> AsyncIterator[bytes]:
    yield body


def _docx(
    *, document: bytes = b"<document/>", relationship: bytes | None = None
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("word/document.xml", document)
        if relationship is not None:
            archive.writestr("word/_rels/document.xml.rels", relationship)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "body",
    [
        b"%PDF-1.7\n/J#61vaScript (synthetic)",
        b"%PDF-1.7\n/Type /ObjStm",
        b"%PDF-1.7\n%%EOF\nsynthetic incremental update\n%%EOF",
    ],
)
async def test_pdf_obfuscation_and_incremental_updates_fail_closed(body: bytes) -> None:
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.result is ScanResult.FAILED
    assert result.reason_code == "ACTIVE_CONTENT"


@pytest.mark.parametrize(
    "body",
    [
        _docx(
            relationship=(
                b'<Relationship TargetMode="External" '
                b'Target="https://external.example/template"/>'
            )
        ),
        _docx(document=b"<w:instrText>DDEAUTO cmd synthetic</w:instrText>"),
    ],
)
async def test_office_external_relationships_and_dde_fail_closed(body: bytes) -> None:
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.result is ScanResult.FAILED
    assert result.reason_code == "ACTIVE_CONTENT"
