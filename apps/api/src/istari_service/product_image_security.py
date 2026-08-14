"""Bounded semantic validation for managed PNG and JPEG artefacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Literal, Protocol, cast

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_DIMENSION = 12_000
MAX_IMAGE_PIXELS = 40_000_000

_FORMAT_BY_EXTENSION = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}
_MODES_BY_FORMAT = {
    "JPEG": frozenset({"CMYK", "L", "RGB"}),
    "PNG": frozenset({"L", "LA", "P", "RGB", "RGBA"}),
}
_SAFE_INFO = {
    "JPEG": frozenset(
        {"dpi", "exif", "jfif", "jfif_density", "jfif_unit", "jfif_version"}
    ),
    "PNG": frozenset({"dpi", "gamma", "srgb", "transparency"}),
}
_PNG_CORE_CHUNKS = frozenset({b"IHDR", b"PLTE", b"IDAT", b"IEND"})
_PNG_SAFE_ANCILLARY_LENGTHS = {
    b"cHRM": 32,
    b"gAMA": 4,
    b"pHYs": 9,
    b"sRGB": 1,
}


class ReadableSeekable(Protocol):
    def read(self, size: int = -1) -> bytes: ...
    def seek(self, offset: int, whence: int = 0) -> int: ...


def inspect_safe_image(stream: ReadableSeekable, extension: str) -> str | None:
    """Fully decode one bounded still image and reject embedded metadata."""

    expected_format = _FORMAT_BY_EXTENSION.get(extension)
    if expected_format is None:
        return "UNSUPPORTED_IMAGE"
    try:
        source = cast(BinaryIO, stream)
        source.seek(0)
        with Image.open(source) as image:
            reason = _validate_image(image, expected_format, inspect_metadata=False)
            if reason:
                return reason
            image.verify()
        source.seek(0)
        with Image.open(source) as decoded:
            reason = _validate_image(decoded, expected_format)
            if reason:
                return reason
            decoded.load()
        if not _has_exact_image_end(source, expected_format):
            return "IMAGE_TRAILING_DATA"
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        RuntimeError,
        UnidentifiedImageError,
        ValueError,
    ):
        return "INVALID_IMAGE"
    return None


def _has_exact_image_end(source: BinaryIO, format_name: str) -> bool:
    source.seek(0)
    content = source.read()
    if format_name == "PNG":
        return _png_ends_exactly(content)
    return _jpeg_ends_exactly(content)


def _png_ends_exactly(content: bytes) -> bool:
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    position = 8
    seen: set[bytes] = set()
    colour_type: int | None = None
    palette_entries = 0
    while position + 12 <= len(content):
        size = int.from_bytes(content[position : position + 4], "big")
        end = position + 12 + size
        if end > len(content):
            return False
        chunk_type = content[position + 4 : position + 8]
        payload = content[position + 8 : position + 8 + size]
        if not _safe_png_chunk(
            chunk_type,
            payload,
            seen=seen,
            colour_type=colour_type,
            palette_entries=palette_entries,
        ):
            return False
        if chunk_type == b"IHDR":
            colour_type = payload[9]
        elif chunk_type == b"PLTE":
            palette_entries = size // 3
        seen.add(chunk_type)
        if chunk_type == b"IEND":
            return size == 0 and end == len(content)
        position = end
    return False


def _safe_png_chunk(
    chunk_type: bytes,
    payload: bytes,
    *,
    seen: set[bytes],
    colour_type: int | None,
    palette_entries: int,
) -> bool:
    if chunk_type == b"IHDR":
        return not seen and len(payload) == 13
    if chunk_type == b"PLTE":
        return (
            b"IHDR" in seen
            and b"IDAT" not in seen
            and b"PLTE" not in seen
            and 0 < len(payload) <= 768
            and len(payload) % 3 == 0
        )
    if chunk_type == b"IDAT":
        return b"IHDR" in seen and b"IEND" not in seen
    if chunk_type == b"IEND":
        return b"IDAT" in seen and b"IEND" not in seen and not payload
    if chunk_type == b"tRNS":
        if colour_type not in {0, 2, 3}:
            return False
        maximum = {0: 2, 2: 6, 3: palette_entries}[colour_type]
        if b"IDAT" in seen or b"tRNS" in seen:
            return False
        return (
            len(payload) == maximum
            if colour_type in {0, 2}
            else 0 < len(payload) <= maximum
        )
    expected_length = _PNG_SAFE_ANCILLARY_LENGTHS.get(chunk_type)
    return (
        expected_length is not None
        and len(payload) == expected_length
        and chunk_type not in seen
        and b"IDAT" not in seen
    )


def _jpeg_ends_exactly(content: bytes) -> bool:
    if not content.startswith(b"\xff\xd8"):
        return False
    position = 2
    in_scan = False
    app_markers: set[int] = set()
    while position < len(content):
        if content[position] != 0xFF:
            if not in_scan:
                return False
            position += 1
            continue
        marker_start = position
        while position < len(content) and content[position] == 0xFF:
            position += 1
        if position >= len(content):
            return False
        marker = content[position]
        position += 1
        if in_scan and (marker == 0x00 or 0xD0 <= marker <= 0xD7):
            continue
        if marker == 0xD9:
            return position == len(content)
        if marker == 0xD8 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            in_scan = False
            continue
        if position + 2 > len(content):
            return False
        segment_size = int.from_bytes(content[position : position + 2], "big")
        if segment_size < 2 or position + segment_size > len(content):
            return False
        payload = content[position + 2 : position + segment_size]
        if 0xE0 <= marker <= 0xEF:
            if marker in app_markers or not _safe_jpeg_app(marker, payload):
                return False
            app_markers.add(marker)
        elif marker == 0xFE:
            return False
        position += segment_size
        in_scan = marker == 0xDA
        if not in_scan and marker_start + 2 >= position:
            return False
    return False


def _safe_jpeg_app(marker: int, payload: bytes) -> bool:
    if marker == 0xE0:
        return _safe_jfif(payload)
    if marker == 0xE1:
        return _safe_orientation_exif(payload)
    if marker == 0xEE:
        return (
            len(payload) == 12
            and payload[:5] == b"Adobe"
            and int.from_bytes(payload[5:7], "big") == 100
            and payload[7:11] == b"\x00\x00\x00\x00"
            and payload[11] in {0, 1, 2}
        )
    return False


def _safe_jfif(payload: bytes) -> bool:
    return (
        len(payload) == 14
        and payload.startswith(b"JFIF\x00")
        and payload[5] == 1
        and payload[6] <= 2
        and payload[7] in {0, 1, 2}
        and payload[8:10] != b"\x00\x00"
        and payload[10:12] != b"\x00\x00"
        and payload[12:] == b"\x00\x00"
    )


@dataclass(frozen=True, slots=True)
class _TiffOrder:
    byte_order: Literal["little", "big"]

    def value(self, content: bytes) -> int:
        return int.from_bytes(content, self.byte_order)


def _safe_orientation_exif(payload: bytes) -> bool:
    if not payload.startswith(b"Exif\x00\x00"):
        return False
    tiff = payload[6:]
    if len(tiff) != 26 or tiff[:2] not in {b"II", b"MM"}:
        return False
    order = _TiffOrder("little" if tiff[:2] == b"II" else "big")
    if order.value(tiff[2:4]) != 42 or order.value(tiff[4:8]) != 8:
        return False
    if order.value(tiff[8:10]) != 1:
        return False
    entry = tiff[10:22]
    tag = order.value(entry[:2])
    field_type = order.value(entry[2:4])
    count = order.value(entry[4:8])
    orientation = order.value(entry[8:10])
    return (
        tag == 0x0112
        and field_type == 3
        and count == 1
        and 1 <= orientation <= 8
        and entry[10:] == b"\x00\x00"
        and tiff[22:] == b"\x00\x00\x00\x00"
    )


def _validate_image(
    image: Image.Image, expected_format: str, *, inspect_metadata: bool = True
) -> str | None:
    if image.format != expected_format:
        return "SIGNATURE_MISMATCH"
    width, height = image.size
    if (
        width < 1
        or height < 1
        or width > MAX_IMAGE_DIMENSION
        or height > MAX_IMAGE_DIMENSION
        or width * height > MAX_IMAGE_PIXELS
    ):
        return "IMAGE_DIMENSIONS_EXCEEDED"
    if getattr(image, "n_frames", 1) != 1:
        return "ANIMATED_IMAGE"
    if image.mode not in _MODES_BY_FORMAT[expected_format]:
        return "UNSUPPORTED_IMAGE_MODE"
    if inspect_metadata and _unsafe_metadata(image, expected_format):
        return "IMAGE_METADATA"
    return None


def _unsafe_metadata(image: Image.Image, expected_format: str) -> bool:
    exif = image.getexif()
    safe_orientation = (
        expected_format == "JPEG"
        and set(exif) == {0x0112}
        and exif.get(0x0112) in range(1, 9)
    )
    return bool(
        (exif and not safe_orientation) or set(image.info) - _SAFE_INFO[expected_format]
    )
