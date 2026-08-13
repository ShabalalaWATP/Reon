"""Strict document and external-link validation without network access."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
import tempfile
import zipfile
from collections.abc import AsyncIterable
from pathlib import PurePath
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from istari_service.product_errors import ProductValidationFailed
from istari_service.product_ports import ScannerAssurance
from istari_service.product_types import ScanDecision, ScanResult
from istari_service.product_zip_preflight import (
    MAX_ZIP_ENTRIES,
    central_directory_preflight,
)

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_PACKAGE_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 125 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
MAX_CONCURRENT_DOCUMENT_SCANS = 4
PPTX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
MEDIA_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": PPTX_MEDIA_TYPE,
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
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
_PDF_ACTIVE = (
    b"/javascript",
    b"/js",
    b"/launch",
    b"/embeddedfile",
    b"/openaction",
    b"/richmedia",
    b"/acroform",
    b"/objstm",
)
_PDF_NAME_ESCAPE = re.compile(rb"#([0-9a-fA-F]{2})")
_EXTERNAL_RELATIONSHIP = re.compile(
    rb"targetmode\s*=\s*['\"]external['\"]", re.IGNORECASE
)
_ACTIVE_XML = (b"ddeauto", b"attachedtemplate", b"oleobject", b"externaldata")
_STANDARD_ZIPFILE = zipfile.ZipFile


class _ReadableSeekable(Protocol):
    def read(self, size: int = -1) -> bytes: ...
    def seek(self, offset: int, whence: int = 0) -> int:
        del offset, whence
        raise NotImplementedError


def _decode_pdf_name(match: re.Match[bytes]) -> bytes:
    return bytes((int(match.group(1), 16),))


def validate_managed_metadata(
    *, filename: str, media_type: str, size_bytes: int, checksum: str
) -> tuple[str, str]:
    """Return a safe filename and canonical media type."""

    if (
        not filename
        or len(filename) > 180
        or PurePath(filename).name != filename
        or "/" in filename
        or "\\" in filename
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
    ):
        raise ProductValidationFailed("The attachment filename is not safe.")
    extension = PurePath(filename).suffix.lower()
    expected_media = MEDIA_BY_EXTENSION.get(extension)
    if expected_media is None or media_type.lower() != expected_media:
        raise ProductValidationFailed("The attachment format is not approved.")
    if not 0 < size_bytes <= MAX_FILE_BYTES:
        raise ProductValidationFailed("The attachment exceeds the file-size limit.")
    normalised_checksum = checksum.lower()
    if not _SHA256.fullmatch(normalised_checksum):
        raise ProductValidationFailed("A valid SHA-256 checksum is required.")
    return filename, expected_media


def normalise_product_correlation_id(value: str | None) -> str | None:
    """Bound audit correlation data and replace unsafe input with a stable digest."""

    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if _SAFE_CORRELATION_ID.fullmatch(candidate):
        return candidate
    encoded = candidate.encode("utf-8", errors="replace")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class SafeDocumentScanner:
    assurance = ScannerAssurance.LOCAL_HEURISTIC

    def __init__(
        self, *, maximum_concurrent_scans: int = MAX_CONCURRENT_DOCUMENT_SCANS
    ) -> None:
        if maximum_concurrent_scans < 1:
            raise ValueError("maximum_concurrent_scans must be positive")
        self._scan_slots = asyncio.Semaphore(maximum_concurrent_scans)

    async def scan(
        self,
        chunks: AsyncIterable[bytes],
        *,
        filename: str,
        declared_media_type: str,
        expected_size: int,
        expected_checksum: str,
    ) -> ScanDecision:
        async with self._scan_slots:
            return await self._scan(
                chunks,
                filename=filename,
                declared_media_type=declared_media_type,
                expected_size=expected_size,
                expected_checksum=expected_checksum,
            )

    async def _scan(
        self,
        chunks: AsyncIterable[bytes],
        *,
        filename: str,
        declared_media_type: str,
        expected_size: int,
        expected_checksum: str,
    ) -> ScanDecision:
        try:
            validate_managed_metadata(
                filename=filename,
                media_type=declared_media_type,
                size_bytes=expected_size,
                checksum=expected_checksum,
            )
            with tempfile.SpooledTemporaryFile(max_size=1_048_576) as stream:
                digest = hashlib.sha256()
                observed_size = 0
                malware_tail = b""
                signature = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
                malware = False
                async for chunk in chunks:
                    observed_size += len(chunk)
                    if observed_size > MAX_FILE_BYTES:
                        return self._failed("SIZE_MISMATCH")
                    digest.update(chunk)
                    malware_window = malware_tail + chunk
                    malware = malware or signature in malware_window
                    malware_tail = malware_window[-(len(signature) - 1) :]
                    stream.write(chunk)
                if (
                    observed_size != expected_size
                    or digest.hexdigest() != expected_checksum
                ):
                    return self._failed("CHECKSUM_MISMATCH")
                if malware:
                    return self._failed("MALWARE_DETECTED")
                stream.seek(0)
                extension = PurePath(filename).suffix.lower()
                reason = (
                    self._inspect_pdf(stream)
                    if extension == ".pdf"
                    else self._inspect_office(stream, extension)
                )
        except (OSError, ValueError, zipfile.BadZipFile):
            reason = "INVALID_CONTAINER"
        return (
            self._failed(reason)
            if reason
            else ScanDecision(
                result=ScanResult.CLEAN,
                scanner="local-safe-document-inspector",
                scanner_version="2",
            )
        )

    @staticmethod
    def _inspect_pdf(stream: _ReadableSeekable) -> str | None:
        if stream.read(5) != b"%PDF-":
            return "SIGNATURE_MISMATCH"
        stream.seek(0)
        content = stream.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            return "ARCHIVE_LIMIT"
        lowered = _PDF_NAME_ESCAPE.sub(_decode_pdf_name, content).lower()
        if b"/encrypt" in lowered:
            return "ENCRYPTED_DOCUMENT"
        if any(marker in lowered for marker in _PDF_ACTIVE):
            return "ACTIVE_CONTENT"
        if lowered.count(b"%%eof") > 1:
            return "ACTIVE_CONTENT"
        return None

    @staticmethod
    def _inspect_office(stream: _ReadableSeekable, extension: str) -> str | None:
        if stream.read(4) != b"PK\x03\x04":
            return "SIGNATURE_MISMATCH"
        stream.seek(0)
        zipfile_type = zipfile.ZipFile
        if isinstance(zipfile_type, type) and issubclass(
            zipfile_type, _STANDARD_ZIPFILE
        ):
            preflight = central_directory_preflight(stream)
            if preflight is not None:
                return preflight
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                return "ARCHIVE_LIMIT"
            total = 0
            names = {entry.filename.lower() for entry in entries}
            for entry in entries:
                if entry.flag_bits & 0x1:
                    return "ENCRYPTED_DOCUMENT"
                total += entry.file_size
                if total > MAX_UNCOMPRESSED_BYTES:
                    return "ARCHIVE_LIMIT"
                if entry.file_size and entry.compress_size == 0:
                    return "ARCHIVE_LIMIT"
                if (
                    entry.compress_size
                    and entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO
                ):
                    return "ARCHIVE_LIMIT"
                lowered = f"/{entry.filename.lower()}"
                if any(marker in lowered for marker in _ACTIVE_PARTS):
                    return "ACTIVE_CONTENT"
                if entry.filename.lower().endswith((".xml", ".rels")):
                    with archive.open(entry) as source:
                        tail = b""
                        while chunk := source.read(65_536):
                            inspected = (tail + chunk).lower()
                            if _EXTERNAL_RELATIONSHIP.search(inspected) or any(
                                marker in inspected for marker in _ACTIVE_XML
                            ):
                                return "ACTIVE_CONTENT"
                            tail = inspected[-64:]
            required = (
                "word/document.xml" if extension == ".docx" else "ppt/presentation.xml"
            )
            if "[content_types].xml" not in names or required not in names:
                return "INVALID_OFFICE_STRUCTURE"
        return None

    @staticmethod
    def _failed(reason: str) -> ScanDecision:
        return ScanDecision(
            result=ScanResult.FAILED,
            scanner="local-safe-document-inspector",
            scanner_version="2",
            reason_code=reason,
        )


class AllowedHttpsLinkPolicy:
    """Exact-domain allow-list validation that never resolves or fetches URLs."""

    def __init__(self, allowed_domains: frozenset[str]) -> None:
        self._allowed = frozenset(self._domain(item) for item in allowed_domains)

    def normalise(self, destination: str) -> tuple[str, str]:
        if (
            not destination
            or any(ord(char) < 32 for char in destination)
            or "\\" in destination
        ):
            raise ProductValidationFailed("The external product link is invalid.")
        parsed = urlsplit(destination)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ProductValidationFailed(
                "An approved absolute HTTPS link is required."
            )
        try:
            port = parsed.port
        except ValueError as exc:
            raise ProductValidationFailed(
                "An approved absolute HTTPS link is required."
            ) from exc
        if port not in {None, 443}:
            raise ProductValidationFailed(
                "An approved absolute HTTPS link is required."
            )
        domain = self._domain(parsed.hostname)
        try:
            address = ipaddress.ip_address(domain)
        except ValueError:
            address = None
        if address is not None and (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ProductValidationFailed(
                "Private-network product links are forbidden."
            )
        if domain not in self._allowed:
            raise ProductValidationFailed(
                "The external product domain is not approved."
            )
        path = parsed.path or "/"
        return urlunsplit(("https", domain, path, parsed.query, "")), domain

    @staticmethod
    def _domain(value: str) -> str:
        try:
            return value.rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ProductValidationFailed(
                "The external product domain is invalid."
            ) from exc
