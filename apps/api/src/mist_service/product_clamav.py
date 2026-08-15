"""Bounded ClamAV INSTREAM malware scanning and defence-in-depth composition."""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from collections.abc import AsyncIterable, AsyncIterator
from typing import Protocol

from mist_service.product_ports import DocumentScanner, ScannerAssurance
from mist_service.product_security import MAX_FILE_BYTES
from mist_service.product_types import ScanDecision, ScanResult


class _BinaryReader(Protocol):
    def read(self, size: int = -1) -> bytes: ...

    def seek(self, offset: int, whence: int = 0) -> int:
        del offset, whence
        raise NotImplementedError


class ClamAvInstreamScanner:
    """Stream one bounded object to clamd without creating scanner-side paths."""

    assurance = ScannerAssurance.MALWARE_SIGNATURE

    def __init__(
        self,
        host: str,
        *,
        port: int = 3310,
        timeout_seconds: float = 30.0,
        maximum_bytes: int = MAX_FILE_BYTES,
    ) -> None:
        if not host or not 1 <= port <= 65_535 or timeout_seconds <= 0:
            raise ValueError("valid ClamAV connection settings are required")
        self._host = host
        self._port = port
        self._timeout = timeout_seconds
        self._maximum_bytes = maximum_bytes

    async def scan(
        self,
        chunks: AsyncIterable[bytes],
        *,
        filename: str,
        declared_media_type: str,
        expected_size: int,
        expected_checksum: str,
    ) -> ScanDecision:
        del filename, declared_media_type
        try:
            return await asyncio.wait_for(
                self._scan(chunks, expected_size, expected_checksum),
                timeout=self._timeout,
            )
        except TimeoutError:
            return self._decision(ScanResult.TIMED_OUT, "SCANNER_TIMEOUT")
        except asyncio.LimitOverrunError:
            return self._decision(ScanResult.UNKNOWN, "SCANNER_RESPONSE_INVALID")
        except (ConnectionError, OSError, asyncio.IncompleteReadError):
            return self._decision(ScanResult.UNKNOWN, "SCANNER_UNAVAILABLE")

    async def _scan(
        self,
        chunks: AsyncIterable[bytes],
        expected_size: int,
        expected_checksum: str,
    ) -> ScanDecision:
        reader, writer = await asyncio.open_connection(
            self._host, self._port, limit=4_096
        )
        observed, digest = 0, hashlib.sha256()
        try:
            writer.write(b"zINSTREAM\0")
            async for chunk in chunks:
                if not chunk:
                    continue
                observed += len(chunk)
                if observed > min(self._maximum_bytes, expected_size):
                    return self._decision(ScanResult.FAILED, "SIZE_MISMATCH")
                digest.update(chunk)
                writer.write(len(chunk).to_bytes(4, "big") + chunk)
                await writer.drain()
            writer.write(b"\0\0\0\0")
            await writer.drain()
            response = await reader.readuntil(b"\0")
        finally:
            writer.close()
            await writer.wait_closed()
        if observed != expected_size or digest.hexdigest() != expected_checksum:
            return self._decision(ScanResult.FAILED, "CHECKSUM_MISMATCH")
        message = response.rstrip(b"\0\r\n")
        if message.endswith(b" FOUND"):
            return self._decision(ScanResult.FAILED, "MALWARE_DETECTED")
        if message.endswith(b" OK"):
            return self._decision(ScanResult.CLEAN)
        return self._decision(ScanResult.UNKNOWN, "SCANNER_RESPONSE_INVALID")

    @staticmethod
    def _decision(result: ScanResult, reason: str | None = None) -> ScanDecision:
        return ScanDecision(
            result=result,
            scanner="clamav-instream",
            scanner_version="1",
            reason_code=reason,
        )


class CompositeDocumentScanner:
    """Require both strict structure validation and malware scanning to pass."""

    assurance = ScannerAssurance.LOCAL_HEURISTIC_AND_MALWARE

    def __init__(
        self,
        structure_scanner: DocumentScanner,
        malware_scanner: DocumentScanner,
        *,
        maximum_bytes: int = MAX_FILE_BYTES,
    ) -> None:
        self._structure = structure_scanner
        self._malware = malware_scanner
        self._maximum_bytes = maximum_bytes

    async def scan(
        self,
        chunks: AsyncIterable[bytes],
        *,
        filename: str,
        declared_media_type: str,
        expected_size: int,
        expected_checksum: str,
    ) -> ScanDecision:
        with tempfile.SpooledTemporaryFile(max_size=1_048_576) as stream:
            observed = 0
            async for chunk in chunks:
                observed += len(chunk)
                if observed > min(self._maximum_bytes, expected_size):
                    return self._failed("SIZE_MISMATCH")
                stream.write(chunk)
            if observed != expected_size:
                return self._failed("SIZE_MISMATCH")

            def source() -> AsyncIterator[bytes]:
                stream.seek(0)
                return self._file_chunks(stream)

            structure = await self._structure.scan(
                source(),
                filename=filename,
                declared_media_type=declared_media_type,
                expected_size=expected_size,
                expected_checksum=expected_checksum,
            )
            if structure.result is not ScanResult.CLEAN:
                return structure
            return await self._malware.scan(
                source(),
                filename=filename,
                declared_media_type=declared_media_type,
                expected_size=expected_size,
                expected_checksum=expected_checksum,
            )

    @staticmethod
    async def _file_chunks(stream: _BinaryReader) -> AsyncIterator[bytes]:
        while chunk := stream.read(65_536):
            yield chunk

    @staticmethod
    def _failed(reason: str) -> ScanDecision:
        return ScanDecision(
            result=ScanResult.FAILED,
            scanner="composite-document-scanner",
            scanner_version="1",
            reason_code=reason,
        )
