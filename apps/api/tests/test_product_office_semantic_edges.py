"""Focused Office semantic controls for decoded fields and relationships."""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import AsyncIterator

from mist_service.product_security import SafeDocumentScanner
from mist_service.product_types import ScanResult

DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _chunks(body: bytes) -> AsyncIterator[bytes]:
    yield body


def _docx(*, document: bytes, relationships: bytes | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("word/document.xml", document)
        if relationships is not None:
            archive.writestr("word/_rels/document.xml.rels", relationships)
    return buffer.getvalue()


async def _scan(body: bytes):
    return await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.docx",
        declared_media_type=DOCX_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )


async def test_office_rejects_encoded_simple_field_instructions() -> None:
    body = _docx(
        document=(
            b'<w:document xmlns:w="urn:synthetic-word">'
            b'<w:fldSimple w:instr="DD&#x45;AUTO synthetic"/>'
            b"</w:document>"
        )
    )

    decision = await _scan(body)

    assert decision.reason_code == "ACTIVE_CONTENT"


async def test_office_accepts_the_standard_core_properties_relationship() -> None:
    relationships = (
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/package/2006/relationships/'
        b'metadata/core-properties" Target="docProps/core.xml"/>'
        b"</Relationships>"
    )
    body = _docx(document=b"<document/>", relationships=relationships)

    decision = await _scan(body)

    assert decision.result is ScanResult.CLEAN
