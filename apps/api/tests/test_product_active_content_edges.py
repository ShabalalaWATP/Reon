"""Adversarial active-content cases for managed product inspection."""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import AsyncIterator

import pytest

from mist_service.product_security import (
    MAX_FILE_BYTES,
    SafeDocumentScanner,
    normalise_product_correlation_id,
    validate_managed_metadata,
)
from mist_service.product_types import ScanResult

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


def test_managed_metadata_normalises_an_approved_format() -> None:
    assert validate_managed_metadata(
        filename="Synthetic Report.PDF",
        media_type="APPLICATION/PDF",
        size_bytes=10,
        checksum="A" * 64,
    ) == ("Synthetic Report.PDF", PDF_MEDIA)


def test_pdf_inspector_rejects_content_above_its_internal_bound() -> None:
    body = b"%PDF-" + (b"x" * (MAX_FILE_BYTES - 4))
    assert SafeDocumentScanner._inspect_pdf(io.BytesIO(body)) == "ARCHIVE_LIMIT"


async def _chunks(body: bytes) -> AsyncIterator[bytes]:
    yield body


def _docx(
    *,
    content_types: bytes = b"<Types/>",
    document: bytes = b"<document/>",
    relationship: bytes | None = None,
    extras: tuple[tuple[str, bytes], ...] = (),
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document)
        if relationship is not None:
            archive.writestr("word/_rels/document.xml.rels", relationship)
        for name, value in extras:
            archive.writestr(name, value)
    return buffer.getvalue()


def _relationships(relationship: bytes) -> bytes:
    return (
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + relationship
        + b"</Relationships>"
    )


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
            relationship=_relationships(
                b'<Relationship TargetMode="External" '
                b'Target="https://external.example/template"/>'
            )
        ),
        _docx(
            document=(
                b'<w:document xmlns:w="urn:synthetic-word"><w:instrText>DDEAUTO cmd '
                b"synthetic</w:instrText></w:document>"
            )
        ),
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


@pytest.mark.parametrize(
    "relationship",
    [
        _relationships(b'<Relationship TargetMode="Ex&#x74;ernal" Target="safe.xml"/>'),
        _relationships(
            b'<Relationship Target="https&#x3a;//external.example/template"/>'
        ),
        _relationships(b'<Relationship Target="/word/template.xml"/>'),
        _relationships(b'<Relationship Target="C:/synthetic/template.xml"/>'),
        _relationships(b'<Relationship Target="\\\\synthetic-host\\share"/>'),
        _relationships(
            b'<Relationship Type="urn:synthetic/oleObj&#x65;ct" Target="safe.bin"/>'
        ),
    ],
)
async def test_office_decodes_relationship_security_fields(
    relationship: bytes,
) -> None:
    body = _docx(relationship=relationship)
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == "ACTIVE_CONTENT"


async def test_office_decodes_active_content_types() -> None:
    body = _docx(
        content_types=(
            b'<Types><Override ContentType="application/vnd.ms-word.document.'
            b'macroEnabl&#x65;d.12"/></Types>'
        )
    )
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == "ACTIVE_CONTENT"


async def test_office_detects_adjacent_encoded_instruction_text() -> None:
    body = _docx(
        document=(
            b'<w:document xmlns:w="urn:synthetic-word">'
            b"<w:instrText>DD&#x45;</w:instrText>"
            b"<w:instrText>AU&#x54;O synthetic</w:instrText>"
            b"</w:document>"
        )
    )
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == "ACTIVE_CONTENT"


@pytest.mark.parametrize("name", [b"U#52I", b"Submit#46orm", b"A#41", b"GoTo#52"])
async def test_pdf_canonicalises_active_capability_names(name: bytes) -> None:
    body = b"%PDF-1.7\n/" + name + b" 1\n%%EOF"
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == "ACTIVE_CONTENT"


@pytest.mark.parametrize(
    "body",
    [
        b"%PDF-1.7\n(URI SubmitForm JavaScript) /Dest /section-one\n%%EOF",
        b"%PDF-1.7\n/S /GoTo /D /section-one\n%%EOF",
    ],
)
async def test_pdf_accepts_text_and_internal_navigation_names(body: bytes) -> None:
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.result is ScanResult.CLEAN


async def test_office_accepts_utf16_and_ordinary_character_references() -> None:
    document = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        '<document title="Safe &#x41;">Ordinary &#65; text</document>'
    ).encode("utf-16")
    body = _docx(document=document)
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.result is ScanResult.CLEAN


async def test_office_accepts_an_internal_relationship() -> None:
    body = _docx(
        relationship=_relationships(
            b'<Relationship Type="urn:synthetic/styles" Target="styles.xml"/>'
        )
    )
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.result is ScanResult.CLEAN


@pytest.mark.parametrize(
    "name",
    ["../word/extra.xml", "Word/document.xml"],
)
async def test_office_rejects_ambiguous_archive_paths(name: str) -> None:
    body = _docx(extras=((name, b"<document/>"),))
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == "INVALID_CONTAINER"


async def test_office_rejects_a_backslash_archive_path() -> None:
    body = _docx(extras=(("word/extra.xml", b"<document/>"),))
    body = body.replace(b"word/extra.xml", b"word\\extra.xml")
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == "INVALID_CONTAINER"


@pytest.mark.parametrize(
    ("document", "reason"),
    [
        (b"<!DOCTYPE document><document/>", "ACTIVE_CONTENT"),
        (
            b'<!DOCTYPE document [<!ENTITY synthetic "safe">]>'
            b"<document>&synthetic;</document>",
            "ACTIVE_CONTENT",
        ),
        (b"<oleObject/>", "ACTIVE_CONTENT"),
        (b"<document>", "INVALID_CONTAINER"),
    ],
)
async def test_office_fails_closed_on_forbidden_or_malformed_xml(
    document: bytes, reason: str
) -> None:
    body = _docx(document=document)
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == reason


@pytest.mark.parametrize(
    "document",
    [
        b"<node>" * 65 + b"</node>" * 65,
        b"<document "
        + b" ".join(f'a{index}="safe"'.encode() for index in range(129))
        + b"/>",
        b'<document title="' + (b"x" * 16_385) + b'"/>',
    ],
)
async def test_office_rejects_excessive_xml_structure(document: bytes) -> None:
    body = _docx(document=document)
    result = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )
    assert result.reason_code == "ARCHIVE_LIMIT"
