"""Semantic image validation at the managed-product scanner boundary."""

from __future__ import annotations

import hashlib
import zlib
from collections.abc import AsyncIterator
from io import BytesIO

import pytest
from PIL import Image, PngImagePlugin

from istari_service.product_security import (
    SafeDocumentScanner,
    validate_managed_metadata,
)
from istari_service.product_types import ScanResult


def _image(format_name: str, *, metadata: bool = False) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (8, 6), color=(20, 40, 60))
    options: dict[str, object] = {}
    if metadata:
        info = PngImagePlugin.PngInfo()
        info.add_text("Comment", "Synthetic hidden metadata")
        options["pnginfo"] = info
    image.save(output, format=format_name, **options)
    return output.getvalue()


async def _chunks(content: bytes) -> AsyncIterator[bytes]:
    yield content[:7]
    yield content[7:]


async def _scan(filename: str, media_type: str, content: bytes):
    return await SafeDocumentScanner().scan(
        _chunks(content),
        filename=filename,
        declared_media_type=media_type,
        expected_size=len(content),
        expected_checksum=hashlib.sha256(content).hexdigest(),
    )


@pytest.mark.parametrize(
    ("filename", "media_type", "format_name"),
    [
        ("map.png", "image/png", "PNG"),
        ("photograph.jpg", "image/jpeg", "JPEG"),
        ("photograph.jpeg", "image/jpeg", "JPEG"),
    ],
)
async def test_safe_still_images_are_fully_decoded(
    filename: str, media_type: str, format_name: str
) -> None:
    content = _image(format_name)
    assert validate_managed_metadata(
        filename=filename,
        media_type=media_type,
        size_bytes=len(content),
        checksum=hashlib.sha256(content).hexdigest(),
    ) == (filename, media_type)
    decision = await _scan(filename, media_type, content)
    assert decision.result is ScanResult.CLEAN


async def test_safe_orientation_and_density_fields_are_preserved() -> None:
    oriented_output = BytesIO()
    orientation = Image.Exif()
    orientation[0x0112] = 6
    Image.new("RGB", (8, 6)).save(oriented_output, format="JPEG", exif=orientation)
    oriented = await _scan("oriented.jpg", "image/jpeg", oriented_output.getvalue())
    assert oriented.result is ScanResult.CLEAN

    density_output = BytesIO()
    Image.new("RGB", (8, 6)).save(density_output, format="PNG", dpi=(96, 96))
    density = await _scan("density.png", "image/png", density_output.getvalue())
    assert density.result is ScanResult.CLEAN


async def test_image_metadata_and_format_spoofing_are_rejected() -> None:
    png = _image("PNG", metadata=True)
    metadata = await _scan("map.png", "image/png", png)
    assert metadata.result is ScanResult.FAILED
    assert metadata.reason_code == "IMAGE_METADATA"

    spoofed = await _scan("map.jpg", "image/jpeg", _image("PNG"))
    assert spoofed.result is ScanResult.FAILED
    assert spoofed.reason_code == "SIGNATURE_MISMATCH"


async def test_corrupt_images_fail_closed() -> None:
    corrupt = b"\x89PNG\r\n\x1a\nsynthetic-corrupt-image"
    decision = await _scan("map.png", "image/png", corrupt)
    assert decision.result is ScanResult.FAILED
    assert decision.reason_code == "INVALID_IMAGE"


@pytest.mark.parametrize(
    ("filename", "media_type", "format_name"),
    [("map.png", "image/png", "PNG"), ("photo.jpg", "image/jpeg", "JPEG")],
)
async def test_image_with_appended_zip_payload_is_rejected(
    filename: str, media_type: str, format_name: str
) -> None:
    polyglot = _image(format_name) + b"PK\x03\x04synthetic-archive-content"
    decision = await _scan(filename, media_type, polyglot)
    assert decision.result is ScanResult.FAILED
    assert decision.reason_code == "IMAGE_TRAILING_DATA"


async def test_png_private_ancillary_payload_is_rejected() -> None:
    png = _image("PNG")
    chunk_type = b"vpAg"
    payload = b"synthetic-private-payload"
    chunk = (
        len(payload).to_bytes(4, "big")
        + chunk_type
        + payload
        + zlib.crc32(chunk_type + payload).to_bytes(4, "big")
    )
    crafted = png[:-12] + chunk + png[-12:]

    decision = await _scan("map.png", "image/png", crafted)

    assert decision.result is ScanResult.FAILED
    assert decision.reason_code == "IMAGE_TRAILING_DATA"


async def test_jpeg_arbitrary_app_payload_is_rejected() -> None:
    jpeg = _image("JPEG")
    payload = b"synthetic-private-payload"
    app_segment = b"\xff\xe3" + (len(payload) + 2).to_bytes(2, "big") + payload
    crafted = jpeg[:2] + app_segment + jpeg[2:]

    decision = await _scan("photo.jpg", "image/jpeg", crafted)

    assert decision.result is ScanResult.FAILED
    assert decision.reason_code == "IMAGE_TRAILING_DATA"
