"""Structural branch coverage for fail-closed PNG and JPEG validation."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest

from istari_service.product_image_security import (
    _jpeg_ends_exactly,
    _png_ends_exactly,
    _safe_jfif,
    _safe_jpeg_app,
    _safe_orientation_exif,
    _safe_png_chunk,
    _validate_image,
    inspect_safe_image,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return len(payload).to_bytes(4, "big") + kind + payload + b"\x00" * 4


def _png(*chunks: tuple[bytes, bytes]) -> bytes:
    return PNG_SIGNATURE + b"".join(_chunk(*chunk) for chunk in chunks)


def _segment(marker: int, payload: bytes = b"") -> bytes:
    return b"\xff" + bytes((marker,)) + (len(payload) + 2).to_bytes(2, "big") + payload


def _exif(
    *,
    byte_order: bytes = b"II",
    magic: int = 42,
    offset: int = 8,
    entries: int = 1,
    orientation: int = 6,
) -> bytes:
    order = "little" if byte_order == b"II" else "big"

    def value(number: int, size: int) -> bytes:
        return number.to_bytes(size, order)

    entry = value(0x0112, 2) + value(3, 2) + value(1, 4)
    entry += value(orientation, 2) + b"\x00\x00"
    tiff = byte_order + value(magic, 2) + value(offset, 4)
    return b"Exif\x00\x00" + tiff + value(entries, 2) + entry + b"\x00" * 4


def test_inspector_and_png_container_fail_closed_on_truncation() -> None:
    assert inspect_safe_image(BytesIO(b"synthetic"), ".gif") == "UNSUPPORTED_IMAGE"
    assert not _png_ends_exactly(b"not-png")
    assert not _png_ends_exactly(PNG_SIGNATURE)
    assert not _png_ends_exactly(
        PNG_SIGNATURE + (20).to_bytes(4, "big") + b"IHDR" + b"short"
    )


def test_palette_png_traverses_the_complete_safe_chunk_sequence() -> None:
    header = b"\x00" * 9 + b"\x03" + b"\x00" * 3
    content = _png(
        (b"IHDR", header),
        (b"PLTE", b"\x00\x00\x00\xff\xff\xff"),
        (b"tRNS", b"\xff\x00"),
        (b"IDAT", b"synthetic"),
        (b"IEND", b""),
    )
    assert _png_ends_exactly(content)


def test_png_palette_transparency_and_ancillary_ordering_are_bounded() -> None:
    assert not _safe_png_chunk(
        b"PLTE", b"", seen=set(), colour_type=3, palette_entries=0
    )
    assert not _safe_png_chunk(
        b"PLTE", b"1234", seen={b"IHDR"}, colour_type=3, palette_entries=0
    )
    assert not _safe_png_chunk(
        b"tRNS", b"x", seen={b"IHDR"}, colour_type=4, palette_entries=0
    )
    assert _safe_png_chunk(
        b"tRNS", b"\x00\x01", seen={b"IHDR"}, colour_type=0, palette_entries=0
    )
    assert _safe_png_chunk(
        b"tRNS", b"\x00" * 6, seen={b"IHDR"}, colour_type=2, palette_entries=0
    )
    assert not _safe_png_chunk(
        b"tRNS", b"x", seen={b"IHDR", b"IDAT"}, colour_type=3, palette_entries=2
    )
    assert _safe_png_chunk(
        b"gAMA", b"\x00" * 4, seen={b"IHDR"}, colour_type=2, palette_entries=0
    )
    assert not _safe_png_chunk(
        b"gAMA",
        b"\x00" * 4,
        seen={b"IHDR", b"gAMA"},
        colour_type=2,
        palette_entries=0,
    )


@pytest.mark.parametrize(
    "content",
    [
        b"not-jpeg",
        b"\xff\xd8",
        b"\xff\xd8raw",
        b"\xff\xd8\xff",
        b"\xff\xd8\xff\xe0\x00",
        b"\xff\xd8\xff\xe0\x00\x01",
        b"\xff\xd8\xff\xe0\x00\x10short",
        b"\xff\xd8" + _segment(0xFE, b"comment") + b"\xff\xd9",
    ],
)
def test_jpeg_container_rejects_malformed_marker_sequences(content: bytes) -> None:
    assert not _jpeg_ends_exactly(content)


def test_jpeg_scan_accepts_only_bounded_entropy_markers_and_exact_end() -> None:
    scan = _segment(0xDA) + b"raw\xff\x00more\xff\xd0data\xff\xd9"
    assert _jpeg_ends_exactly(b"\xff\xd8" + scan)
    assert _jpeg_ends_exactly(b"\xff\xd8\xff\xd0\xff\xd9")


def test_jpeg_application_metadata_allow_lists_are_exact() -> None:
    jfif = b"JFIF\x00\x01\x02\x01\x00\x01\x00\x01\x00\x00"
    assert _safe_jfif(jfif)
    assert not _safe_jfif(jfif[:-1])
    assert not _safe_jpeg_app(0xE3, b"synthetic")
    adobe = b"Adobe" + (100).to_bytes(2, "big") + b"\x00" * 4 + b"\x02"
    assert _safe_jpeg_app(0xEE, adobe)
    assert not _safe_jpeg_app(0xEE, adobe[:-1])


@pytest.mark.parametrize(
    "payload",
    [
        b"not-exif",
        b"Exif\x00\x00short",
        _exif(byte_order=b"MM", magic=41),
        _exif(offset=9),
        _exif(entries=2),
        _exif(orientation=9),
    ],
)
def test_exif_orientation_envelope_rejects_every_structural_deviation(
    payload: bytes,
) -> None:
    assert not _safe_orientation_exif(payload)


@pytest.mark.parametrize(
    ("image", "reason"),
    [
        (
            SimpleNamespace(format="PNG", size=(0, 1), n_frames=1, mode="RGB"),
            "IMAGE_DIMENSIONS_EXCEEDED",
        ),
        (
            SimpleNamespace(format="PNG", size=(1, 1), n_frames=2, mode="RGB"),
            "ANIMATED_IMAGE",
        ),
        (
            SimpleNamespace(format="PNG", size=(1, 1), n_frames=1, mode="CMYK"),
            "UNSUPPORTED_IMAGE_MODE",
        ),
    ],
)
def test_decoded_image_shape_and_mode_are_bounded(
    image: SimpleNamespace, reason: str
) -> None:
    assert _validate_image(image, "PNG", inspect_metadata=False) == reason
