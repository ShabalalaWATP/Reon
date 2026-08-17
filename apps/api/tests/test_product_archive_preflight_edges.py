"""Classic-ZIP metadata edge cases rejected before parser allocation."""

from __future__ import annotations

import io
import struct
import zipfile

from mist_service.product_zip_preflight import central_directory_preflight


def _office_archive(*, directory: bool = False) -> bytearray:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        if directory:
            archive.writestr("word/", b"")
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("word/document.xml", b"<document/>")
    return bytearray(buffer.getvalue())


def test_preflight_accepts_a_canonical_directory_entry() -> None:
    assert (
        central_directory_preflight(io.BytesIO(_office_archive(directory=True))) is None
    )


def test_preflight_rejects_an_inconsistent_archive_comment() -> None:
    body = _office_archive()
    eocd = body.rfind(b"PK\x05\x06")
    struct.pack_into("<H", body, eocd + 20, 1)
    assert central_directory_preflight(io.BytesIO(body)) == "INVALID_CONTAINER"


def test_preflight_rejects_invalid_utf8_entry_names() -> None:
    body = _office_archive()
    central = body.find(b"PK\x01\x02")
    flags = struct.unpack_from("<H", body, central + 8)[0]
    struct.pack_into("<H", body, central + 8, flags | 0x800)
    body[central + 46] = 0xFF
    assert central_directory_preflight(io.BytesIO(body)) == "INVALID_CONTAINER"


def test_preflight_rejects_entry_metadata_beyond_the_central_directory() -> None:
    body = _office_archive()
    central = body.find(b"PK\x01\x02")
    eocd = body.rfind(b"PK\x05\x06")
    central_size = struct.unpack_from("<L", body, eocd + 12)[0]
    struct.pack_into("<H", body, central + 30, central_size)
    assert central_directory_preflight(io.BytesIO(body)) == "INVALID_CONTAINER"


def test_preflight_rejects_unclaimed_central_directory_entries() -> None:
    body = _office_archive()
    eocd = body.rfind(b"PK\x05\x06")
    struct.pack_into("<H", body, eocd + 8, 1)
    struct.pack_into("<H", body, eocd + 10, 1)
    assert central_directory_preflight(io.BytesIO(body)) == "INVALID_CONTAINER"
