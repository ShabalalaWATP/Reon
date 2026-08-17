"""Bounded lexical inspection for the deliberately restricted local PDF subset."""

from __future__ import annotations

import re
from typing import Protocol

MAX_FILE_BYTES = 25 * 1024 * 1024

_ACTIVE_NAMES = {
    b"3d",
    b"aa",
    b"acroform",
    b"af",
    b"col" + b"lection",
    b"embeddedfile",
    b"fileattachment",
    b"goto3dview",
    b"gotoe",
    b"gotor",
    b"hide",
    b"importdata",
    b"javascript",
    b"js",
    b"launch",
    b"movie",
    b"named",
    b"objstm",
    b"openaction",
    b"prc",
    b"rendition",
    b"resetform",
    b"richmedia",
    b"setocgstate",
    b"sound",
    b"submitform",
    b"thread",
    b"trans",
    b"u3d",
    b"uri",
    b"xfa",
}
_DELIMITERS = b"\x00\t\n\f\r ()<>[]{}/%"
_NAME_ESCAPE = re.compile(rb"#([0-9a-fA-F]{2})")
_END_STREAM = re.compile(rb"(?:\r\n|\r|\n)endstream(?=[\x00\t\n\f\r ()<>\[\]{}/%]|$)")


class ReadableSeekable(Protocol):
    def read(self, size: int = -1) -> bytes: ...

    def seek(self, offset: int, whence: int = 0) -> int: ...


def inspect_pdf(stream: ReadableSeekable) -> str | None:
    """Reject active name objects while ignoring inert strings, comments and streams."""
    if stream.read(5) != b"%PDF-":
        return "SIGNATURE_MISMATCH"
    stream.seek(0)
    content = stream.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        return "ARCHIVE_LIMIT"
    names, valid = _name_objects(content)
    if not valid:
        return "INVALID_CONTAINER"
    if b"encrypt" in names:
        return "ENCRYPTED_DOCUMENT"
    if names.intersection(_ACTIVE_NAMES) or content.lower().count(b"%%eof") > 1:
        return "ACTIVE_CONTENT"
    return None


def _name_objects(content: bytes) -> tuple[set[bytes], bool]:
    names: set[bytes] = set()
    cursor = 0
    while cursor < len(content):
        byte = content[cursor]
        if byte == ord("%"):
            cursor = _line_end(content, cursor + 1)
        elif byte == ord("("):
            cursor = _literal_end(content, cursor + 1)
            if cursor < 0:
                return names, False
        elif content.startswith(b"<<", cursor):
            cursor += 2
        elif byte == ord("<"):
            cursor = content.find(b">", cursor + 1)
            if cursor < 0:
                return names, False
            cursor += 1
        elif content.startswith(b">>", cursor):
            stream_start = _stream_start(content, cursor + 2)
            if stream_start is None:
                cursor += 2
                continue
            stream_end = _END_STREAM.search(content, stream_start)
            if stream_end is None:
                return names, False
            cursor = stream_end.end()
        elif byte == ord("/"):
            end = cursor + 1
            while end < len(content) and content[end] not in _DELIMITERS:
                end += 1
            if end > cursor + 1:
                names.add(
                    _NAME_ESCAPE.sub(_decode_name, content[cursor + 1 : end]).lower()
                )
            cursor = end
        else:
            cursor += 1
    return names, True


def _stream_start(content: bytes, cursor: int) -> int | None:
    cursor = _skip_layout(content, cursor)
    if not content.startswith(b"stream", cursor):
        return None
    cursor += len(b"stream")
    if content.startswith(b"\r\n", cursor):
        return cursor + 2
    if cursor < len(content) and content[cursor] in b"\r\n":
        return cursor + 1
    return None


def _skip_layout(content: bytes, cursor: int) -> int:
    while cursor < len(content):
        if content[cursor] in b"\x00\t\n\f\r ":
            cursor += 1
        elif content[cursor] == ord("%"):
            cursor = _line_end(content, cursor + 1)
        else:
            return cursor
    return cursor


def _line_end(content: bytes, cursor: int) -> int:
    while cursor < len(content) and content[cursor] not in b"\r\n":
        cursor += 1
    return cursor


def _literal_end(content: bytes, cursor: int) -> int:
    depth = 1
    while cursor < len(content):
        if content[cursor] == ord("\\"):
            cursor += 2
        elif content[cursor] == ord("("):
            depth += 1
            cursor += 1
        elif content[cursor] == ord(")"):
            depth -= 1
            cursor += 1
            if depth == 0:
                return cursor
        else:
            cursor += 1
    return -1


def _decode_name(match: re.Match[bytes]) -> bytes:
    return bytes((int(match.group(1), 16),))
