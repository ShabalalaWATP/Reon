"""Bounded classic-ZIP central-directory validation before parser allocation."""

from __future__ import annotations

import struct
from pathlib import PurePosixPath
from typing import Protocol

MAX_ZIP_ENTRIES = 1_000
MAX_ZIP_CENTRAL_DIRECTORY_BYTES = 4 * 1024 * 1024


class ReadableSeekable(Protocol):
    def read(self, size: int = -1) -> bytes: ...

    def seek(self, offset: int, whence: int = 0) -> int: ...


def central_directory_preflight(stream: ReadableSeekable) -> str | None:
    """Reject Zip64, multi-disk and excessive metadata before ``ZipFile``."""

    stream.seek(0, 2)
    size = stream.seek(0, 1)
    tail_size = min(size, 65_557)
    stream.seek(size - tail_size)
    tail = stream.read(tail_size)
    position = tail.rfind(b"PK\x05\x06")
    if position < 0 or position + 22 > len(tail):
        return "INVALID_CONTAINER"
    eocd_offset = size - tail_size + position
    (
        _,
        disk,
        central_disk,
        disk_entries,
        entries,
        central_size,
        central_offset,
        comment,
    ) = struct.unpack_from("<4s4H2LH", tail, position)
    if position + 22 + comment != len(tail):
        return "INVALID_CONTAINER"
    if (
        disk != 0
        or central_disk != 0
        or disk_entries != entries
        or entries > MAX_ZIP_ENTRIES
        or central_size > MAX_ZIP_CENTRAL_DIRECTORY_BYTES
        or central_offset + central_size != eocd_offset
        or 0xFFFF in {disk_entries, entries}
        or 0xFFFFFFFF in {central_size, central_offset}
    ):
        return "ARCHIVE_LIMIT"
    stream.seek(central_offset)
    central = stream.read(central_size)
    cursor = 0
    names: set[str] = set()
    for _ in range(entries):
        if cursor + 46 > len(central) or central[cursor : cursor + 4] != b"PK\x01\x02":
            return "INVALID_CONTAINER"
        compressed, expanded = struct.unpack_from("<LL", central, cursor + 20)
        name_length, extra_length, comment_length, disk_start = struct.unpack_from(
            "<4H", central, cursor + 28
        )
        local_offset = struct.unpack_from("<L", central, cursor + 42)[0]
        if (
            0xFFFFFFFF in {compressed, expanded, local_offset}
            or disk_start == 0xFFFF
            or name_length == 0
        ):
            return "ARCHIVE_LIMIT"
        flags = struct.unpack_from("<H", central, cursor + 8)[0]
        raw_name = central[cursor + 46 : cursor + 46 + name_length]
        try:
            name = raw_name.decode("utf-8" if flags & 0x800 else "cp437")
        except UnicodeDecodeError:
            return "INVALID_CONTAINER"
        canonical_name = str(PurePosixPath(name)).casefold()
        parts = name.split("/")
        if name.endswith("/"):
            parts = parts[:-1]
        if (
            b"\\" in raw_name
            or b"\x00" in raw_name
            or name.startswith("/")
            or not parts
            or any(part in {"", ".", ".."} for part in parts)
            or ":" in parts[0]
            or canonical_name in names
        ):
            return "INVALID_CONTAINER"
        names.add(canonical_name)
        cursor += 46 + name_length + extra_length + comment_length
        if cursor > len(central):
            return "INVALID_CONTAINER"
    return None if cursor == len(central) else "INVALID_CONTAINER"
