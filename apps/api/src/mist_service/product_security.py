"""Strict document and external-link validation without network access."""

from __future__ import annotations

import asyncio
import hashlib
import re
import tempfile
import zipfile
from collections.abc import AsyncIterable
from pathlib import PurePath
from typing import Protocol

from mist_service.product_document_security import (
    MAX_UNCOMPRESSED_BYTES as MAX_UNCOMPRESSED_BYTES,
)
from mist_service.product_document_security import inspect_office
from mist_service.product_errors import ProductValidationFailed
from mist_service.product_image_security import inspect_safe_image
from mist_service.product_link_security import (
    AllowedHttpsLinkPolicy as AllowedHttpsLinkPolicy,
)
from mist_service.product_pdf_security import inspect_pdf
from mist_service.product_ports import ScannerAssurance
from mist_service.product_types import ScanDecision, ScanResult

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_PACKAGE_BYTES = 100 * 1024 * 1024
MAX_CONCURRENT_DOCUMENT_SCANS = 4
PPTX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
MEDIA_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": PPTX_MEDIA_TYPE,
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")


class _ReadableSeekable(Protocol):
    def read(self, size: int = -1) -> bytes: ...
    def seek(self, offset: int, whence: int = 0) -> int:
        del offset, whence
        raise NotImplementedError


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
                if extension == ".pdf":
                    reason = self._inspect_pdf(stream)
                elif extension in {".docx", ".pptx"}:
                    reason = self._inspect_office(stream, extension)
                else:
                    reason = inspect_safe_image(stream, extension)
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
        return inspect_pdf(stream)

    @staticmethod
    def _inspect_office(stream: _ReadableSeekable, extension: str) -> str | None:
        return inspect_office(stream, extension, zipfile_type=zipfile.ZipFile)

    @staticmethod
    def _failed(reason: str) -> ScanDecision:
        return ScanDecision(
            result=ScanResult.FAILED,
            scanner="local-safe-document-inspector",
            scanner_version="2",
            reason_code=reason,
        )
