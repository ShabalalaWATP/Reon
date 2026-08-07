"""Replaceable private storage, scanning, link-policy and audit ports."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from istari_service.product_types import (
    AccessAuditRecord,
    DownloadStream,
    ScanDecision,
    StoredObject,
    UploadGrant,
)


class PrivateObjectStorage(Protocol):
    async def issue_upload(
        self, object_key: str, *, expires_at: datetime
    ) -> UploadGrant: ...

    async def write_quarantine(
        self,
        object_key: str,
        chunks: AsyncIterable[bytes],
        *,
        maximum_bytes: int,
    ) -> StoredObject: ...

    async def read_quarantine(self, object_key: str) -> StoredObject: ...

    def stream_quarantine(self, object_key: str) -> AsyncIterator[bytes]: ...

    async def promote(self, quarantine_key: str, released_key: str) -> None: ...

    async def download(
        self, released_key: str, *, filename: str, media_type: str
    ) -> DownloadStream: ...

    async def delete_quarantine(self, object_key: str) -> None: ...


class ScannerAssurance(StrEnum):
    """Security meaning of a scanner result at the application boundary."""

    LOCAL_HEURISTIC = "LOCAL_HEURISTIC"
    MALWARE_SIGNATURE = "MALWARE_SIGNATURE"
    LOCAL_HEURISTIC_AND_MALWARE = "LOCAL_HEURISTIC_AND_MALWARE"
    APPROVED_SEMANTIC_CDR = "APPROVED_SEMANTIC_CDR"


class DocumentScanner(Protocol):
    @property
    def assurance(self) -> ScannerAssurance: ...

    async def scan(
        self,
        chunks: AsyncIterable[bytes],
        *,
        filename: str,
        declared_media_type: str,
        expected_size: int,
        expected_checksum: str,
    ) -> ScanDecision: ...


class ExternalLinkPolicy(Protocol):
    def normalise(self, destination: str) -> tuple[str, str]: ...


class ProductAccessAudit(Protocol):
    async def record(self, record: AccessAuditRecord) -> None: ...
