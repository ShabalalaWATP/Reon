"""Durable private filesystem storage for local development."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import shutil
import tempfile
from collections.abc import AsyncIterable, AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe

from istari_service.product_errors import (
    ProductDependencyUnavailable,
    ProductValidationFailed,
)
from istari_service.product_types import DownloadStream, StoredObject, UploadGrant


class PrivateFilesystemObjectStorage:
    """Atomic, root-contained storage with no HTTP-addressable object paths."""

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()
        self._grants: dict[str, UploadGrant] = {}
        for area in ("quarantine", "released"):
            path = self._root / area
            path.mkdir(parents=True, exist_ok=True)
            self._restrict(path, 0o700)

    async def issue_upload(
        self, object_key: str, *, expires_at: datetime
    ) -> UploadGrant:
        self._path(object_key, "quarantine")
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
        destination = self._path(object_key, "quarantine")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._restrict(destination.parent, 0o700)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".upload-", dir=destination.parent
        )
        temporary = Path(temporary_name)
        digest = hashlib.sha256()
        observed = 0
        try:
            self._restrict(temporary, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    observed += len(chunk)
                    if observed > maximum_bytes:
                        raise ProductValidationFailed(
                            "The attachment exceeds the upload limit."
                        )
                    digest.update(chunk)
                    await asyncio.to_thread(handle.write, chunk)
                await asyncio.to_thread(handle.flush)
                await asyncio.to_thread(os.fsync, handle.fileno())
            await asyncio.to_thread(os.replace, temporary, destination)
            self._restrict(destination, 0o600)
        except BaseException:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
            raise
        return StoredObject(
            size_bytes=observed,
            media_type="application/octet-stream",
            checksum=digest.hexdigest(),
        )

    async def read_quarantine(self, object_key: str) -> StoredObject:
        path = self._existing(object_key, "quarantine")
        size, digest = await asyncio.to_thread(self._metadata, path)
        return StoredObject(
            size_bytes=size,
            media_type="application/octet-stream",
            checksum=digest,
        )

    def stream_quarantine(self, object_key: str) -> AsyncIterator[bytes]:
        return self._chunks(self._existing(object_key, "quarantine"))

    async def promote(self, quarantine_key: str, released_key: str) -> None:
        source = self._existing(quarantine_key, "quarantine")
        destination = self._path(released_key, "released")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._restrict(destination.parent, 0o700)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".release-", dir=destination.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            await asyncio.to_thread(shutil.copyfile, source, temporary)
            await asyncio.to_thread(os.replace, temporary, destination)
        except BaseException:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
            raise
        self._restrict(destination, 0o600)

    async def download(
        self, released_key: str, *, filename: str, media_type: str
    ) -> DownloadStream:
        path = self._existing(released_key, "released")
        return DownloadStream(
            chunks=self._chunks(path), media_type=media_type, filename=filename
        )

    async def delete_quarantine(self, object_key: str) -> None:
        path = self._path(object_key, "quarantine")
        await asyncio.to_thread(path.unlink, True)

    def _path(self, object_key: str, area: str) -> Path:
        if not object_key or "\\" in object_key:
            raise ProductValidationFailed("The private object key is invalid.")
        candidate = (self._root / object_key).resolve()
        area_root = (self._root / area).resolve()
        try:
            candidate.relative_to(area_root)
        except ValueError as exc:
            raise ProductValidationFailed("The private object key is invalid.") from exc
        return candidate

    def _existing(self, object_key: str, area: str) -> Path:
        path = self._path(object_key, area)
        if not path.is_file():
            raise ProductDependencyUnavailable()
        return path

    @staticmethod
    async def _chunks(path: Path) -> AsyncIterator[bytes]:
        with path.open("rb") as handle:
            while chunk := await asyncio.to_thread(handle.read, 65_536):
                yield chunk

    @staticmethod
    def _metadata(path: Path) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(65_536):
                size += len(chunk)
                digest.update(chunk)
        return size, digest.hexdigest()

    @staticmethod
    def _restrict(path: Path, mode: int) -> None:
        # Windows ACLs are configured by the containing local directory.
        with contextlib.suppress(OSError):
            path.chmod(mode)
