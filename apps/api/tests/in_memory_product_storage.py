"""In-memory managed-product storage used only by tests."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterable, AsyncIterator
from datetime import UTC, datetime
from secrets import token_urlsafe

from istari_service.product_errors import (
    ProductDependencyUnavailable,
    ProductValidationFailed,
)
from istari_service.product_types import DownloadStream, StoredObject, UploadGrant


class InMemoryPrivateObjectStorage:
    """Bounded fake storage with no URL or filesystem exposure."""

    def __init__(self) -> None:
        self._quarantine: dict[str, tuple[StoredObject, bytes]] = {}
        self._released: dict[str, tuple[StoredObject, bytes]] = {}
        self._grants: dict[str, UploadGrant] = {}

    async def issue_upload(
        self, object_key: str, *, expires_at: datetime
    ) -> UploadGrant:
        existing = self._grants.get(object_key)
        if existing is not None and existing.expires_at > datetime.now(UTC):
            return existing
        grant = UploadGrant(
            object_key=object_key,
            token=token_urlsafe(32),
            expires_at=expires_at,
        )
        self._grants[object_key] = grant
        return grant

    async def write_quarantine(
        self,
        object_key: str,
        chunks: AsyncIterable[bytes],
        *,
        maximum_bytes: int,
    ) -> StoredObject:
        payload = bytearray()
        async for chunk in chunks:
            if not chunk:
                continue
            if len(payload) + len(chunk) > maximum_bytes:
                raise ProductValidationFailed(
                    "The attachment exceeds the upload limit."
                )
            payload.extend(chunk)
        body = bytes(payload)
        stored = StoredObject(
            size_bytes=len(body),
            media_type="application/octet-stream",
            checksum=hashlib.sha256(body).hexdigest(),
        )
        self._quarantine[object_key] = (stored, body)
        return stored

    async def read_quarantine(self, object_key: str) -> StoredObject:
        try:
            return self._quarantine[object_key][0]
        except KeyError as exc:
            raise ProductDependencyUnavailable() from exc

    async def promote(self, quarantine_key: str, released_key: str) -> None:
        try:
            self._released[released_key] = self._quarantine[quarantine_key]
        except KeyError as exc:
            raise ProductDependencyUnavailable() from exc

    async def download(
        self, released_key: str, *, filename: str, media_type: str
    ) -> DownloadStream:
        try:
            _stored, body = self._released[released_key]
        except KeyError as exc:
            raise ProductDependencyUnavailable() from exc
        return DownloadStream(
            chunks=self._chunks(body), media_type=media_type, filename=filename
        )

    def stream_quarantine(self, object_key: str) -> AsyncIterator[bytes]:
        try:
            _stored, body = self._quarantine[object_key]
        except KeyError as exc:
            raise ProductDependencyUnavailable() from exc
        return self._chunks(body)

    @staticmethod
    async def _chunks(body: bytes) -> AsyncIterator[bytes]:
        for offset in range(0, len(body), 65_536):
            yield body[offset : offset + 65_536]

    async def delete_quarantine(self, object_key: str) -> None:
        self._quarantine.pop(object_key, None)
