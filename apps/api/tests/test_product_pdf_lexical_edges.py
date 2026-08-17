"""Legitimate PDF lexical contexts must not be treated as active name objects."""

from __future__ import annotations

import hashlib
import io
from collections.abc import AsyncIterator

import pytest

from mist_service.product_pdf_security import inspect_pdf
from mist_service.product_security import SafeDocumentScanner
from mist_service.product_types import ScanResult

PDF_MEDIA = "application/pdf"


async def _chunks(body: bytes) -> AsyncIterator[bytes]:
    yield body


@pytest.mark.parametrize(
    "body",
    [
        b"%PDF-1.7\n(Literal /URI text)\n%%EOF",
        b"%PDF-1.7\n% inert /SubmitForm comment\n%%EOF",
        (
            b"%PDF-1.7\n1 0 obj\n<< /Length 11 >>\nstream\n"
            b"/JavaScript\nendstream\nendobj\n%%EOF"
        ),
    ],
)
async def test_pdf_ignores_active_words_in_inert_lexical_contexts(body: bytes) -> None:
    decision = await SafeDocumentScanner().scan(
        _chunks(body),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=len(body),
        expected_checksum=hashlib.sha256(body).hexdigest(),
    )

    assert decision.result is ScanResult.CLEAN


@pytest.mark.parametrize(
    "body",
    [
        b"%PDF-1.7\n(unclosed literal",
        b"%PDF-1.7\n<4142",
        b"%PDF-1.7\n<<>>\nstream\ntruncated",
    ],
)
def test_pdf_rejects_truncated_lexical_contexts(body: bytes) -> None:
    assert inspect_pdf(io.BytesIO(body)) == "INVALID_CONTAINER"


def test_pdf_accepts_nested_strings_empty_names_and_crlf_streams() -> None:
    body = (
        b"%PDF-1.7\n(nested (value\\) /URI))\n/ \n<4142>\n"
        b"<<>> % inert layout comment\r\nstream\r\n"
        b"/JavaScript\r\nendstream\n%%EOF"
    )

    assert inspect_pdf(io.BytesIO(body)) is None


@pytest.mark.parametrize(
    "suffix",
    [b"<<>>\nnotstream\n%%EOF", b"<<>>stream x\n%%EOF", b"<<>>", b"<<>>stream"],
)
def test_pdf_accepts_dictionary_closures_without_stream_bodies(suffix: bytes) -> None:
    assert inspect_pdf(io.BytesIO(b"%PDF-1.7\n" + suffix)) is None
