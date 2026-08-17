"""Bounded semantic inspection for the local Office and PDF subset."""

from __future__ import annotations

import re
import zipfile
from pathlib import PurePosixPath
from typing import Any, Protocol
from urllib.parse import urlsplit

from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]
from defusedxml.ElementTree import ParseError, iterparse  # type: ignore[import-untyped]

from mist_service.product_zip_preflight import (
    MAX_ZIP_ENTRIES,
    central_directory_preflight,
)

MAX_UNCOMPRESSED_BYTES = 125 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
MAX_XML_DEPTH = 64
MAX_XML_NODES = 250_000
MAX_XML_ATTRIBUTES = 128
MAX_XML_ATTRIBUTE_LENGTH = 16_384

_ACTIVE_PARTS = (
    "vbaproject.bin",
    "/activex/",
    "/embeddings/",
    "oleobject",
    ".exe",
    ".js",
    ".vbs",
    "/externallinks/",
    "attachedtemplate",
)
_ACTIVE_XML_NAMES = {"attachedtemplate", "externaldata", "oleobject"}
_ACTIVE_RELATIONSHIP_TYPES = {
    "attachedtemplate",
    "control",
    "externallink",
    "oleobject",
    "package",
    "vbaproject",
}
_ACTIVE_CONTENT_TYPES = (
    "activex",
    "macroenabled",
    "oleobject",
    "vbaproject",
)
_STANDARD_ZIPFILE = zipfile.ZipFile


class ReadableSeekable(Protocol):
    def read(self, size: int = -1) -> bytes: ...

    def seek(self, offset: int, whence: int = 0) -> int: ...


def inspect_office(
    stream: ReadableSeekable, extension: str, *, zipfile_type: Any
) -> str | None:
    if stream.read(4) != b"PK\x03\x04":
        return "SIGNATURE_MISMATCH"
    stream.seek(0)
    if isinstance(zipfile_type, type) and issubclass(zipfile_type, _STANDARD_ZIPFILE):
        preflight = central_directory_preflight(stream)
        if preflight is not None:
            return preflight
    stream.seek(0)
    with zipfile_type(stream) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ZIP_ENTRIES:
            return "ARCHIVE_LIMIT"
        if not _archive_names_are_unambiguous(entries):
            return "INVALID_CONTAINER"
        total = 0
        names = {entry.filename.lower() for entry in entries}
        for entry in entries:
            reason, total = _validate_entry(entry, total)
            if reason:
                return reason
            lowered = f"/{entry.filename.lower()}"
            if any(marker in lowered for marker in _ACTIVE_PARTS):
                return "ACTIVE_CONTENT"
            if entry.filename.lower().endswith((".xml", ".rels")):
                with archive.open(entry) as source:
                    reason = _inspect_xml(source)
                if reason:
                    return reason
        required = (
            "word/document.xml" if extension == ".docx" else "ppt/presentation.xml"
        )
        if "[content_types].xml" not in names or required not in names:
            return "INVALID_OFFICE_STRUCTURE"
    return None


def _validate_entry(entry: zipfile.ZipInfo, total: int) -> tuple[str | None, int]:
    if entry.flag_bits & 0x1:
        return "ENCRYPTED_DOCUMENT", total
    total += entry.file_size
    if total > MAX_UNCOMPRESSED_BYTES:
        return "ARCHIVE_LIMIT", total
    if entry.file_size and entry.compress_size == 0:
        return "ARCHIVE_LIMIT", total
    if (
        entry.compress_size
        and entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO
    ):
        return "ARCHIVE_LIMIT", total
    return None, total


def _archive_names_are_unambiguous(entries: list[zipfile.ZipInfo]) -> bool:
    seen: set[str] = set()
    for entry in entries:
        name = entry.filename
        path = PurePosixPath(name)
        parts = name.split("/")
        if getattr(entry, "is_dir", lambda: False)() and parts[-1] == "":
            parts = parts[:-1]
        folded = str(path).casefold()
        if (
            not name
            or "\\" in name
            or "\x00" in name
            or name.startswith("/")
            or not parts
            or any(part in {"", ".", ".."} for part in parts)
            or ":" in parts[0]
            or folded in seen
        ):
            return False
        seen.add(folded)
    return True


def _inspect_xml(source: object) -> str | None:
    depth = nodes = 0
    instruction_tail = ""
    try:
        for event, element in iterparse(
            source,
            events=("start", "end"),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        ):
            if event == "start":
                depth += 1
                nodes += 1
                if (
                    depth > MAX_XML_DEPTH
                    or nodes > MAX_XML_NODES
                    or len(element.attrib) > MAX_XML_ATTRIBUTES
                    or any(
                        len(name) > MAX_XML_ATTRIBUTE_LENGTH
                        or len(value) > MAX_XML_ATTRIBUTE_LENGTH
                        for name, value in element.attrib.items()
                    )
                ):
                    return "ARCHIVE_LIMIT"
                if _active_element(element.tag, element.attrib):
                    return "ACTIVE_CONTENT"
                continue
            if _local_name(element.tag) == "instrtext":
                instruction = instruction_tail + "".join(element.itertext())
                compact = "".join(instruction.lower().split())
                if "ddeauto" in compact:
                    return "ACTIVE_CONTENT"
                instruction_tail = compact[-32:]
            element.clear()
            depth -= 1
    except DefusedXmlException:
        return "ACTIVE_CONTENT"
    except (ParseError, UnicodeError, ValueError):
        return "INVALID_CONTAINER"
    return None


def _active_element(tag: str, attributes: dict[str, str]) -> bool:
    local = _local_name(tag)
    if local in _ACTIVE_XML_NAMES:
        return True
    values = {
        _local_name(name): value.strip().lower() for name, value in attributes.items()
    }
    if local == "fldsimple":
        instruction = "".join(values.get("instr", "").split())
        if "ddeauto" in instruction:
            return True
    if local == "relationship":
        if values.get("targetmode") == "external":
            return True
        target = values.get("target", "")
        parsed_target = urlsplit(target)
        if (
            target.startswith(("/", "\\"))
            or parsed_target.scheme
            or parsed_target.netloc
            or re.match(r"^[a-z]:", target, re.IGNORECASE)
        ):
            return True
        relation_type = values.get("type", "")
        relationship_name = urlsplit(relation_type).path.rstrip("/").rsplit("/", 1)[-1]
        if relationship_name in _ACTIVE_RELATIONSHIP_TYPES:
            return True
    if local in {"default", "override"}:
        content_type = values.get("contenttype", "")
        if any(marker in content_type for marker in _ACTIVE_CONTENT_TYPES):
            return True
    return False


def _local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1].lower()
