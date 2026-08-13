"""Durable private filesystem storage for local development."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import shutil
import stat
import tempfile
import threading
from collections.abc import AsyncIterable, AsyncIterator
from datetime import UTC, datetime
from pathlib import Path, PurePath
from secrets import token_urlsafe

from istari_service.product_errors import (
    ProductDependencyUnavailable,
    ProductValidationFailed,
)
from istari_service.product_quarantine_index import QuarantineIndex
from istari_service.product_types import DownloadStream, StoredObject, UploadGrant


class PrivateFilesystemObjectStorage:
    """Atomic, root-contained storage with no HTTP-addressable object paths."""

    def __init__(self, root: Path, *, maximum_grants: int = 10_000) -> None:
        if maximum_grants < 1:
            raise ValueError("maximum_grants must be positive")
        self._root = root.expanduser().resolve()
        self._grants: dict[str, UploadGrant] = {}
        self._maximum_grants = maximum_grants
        self._grant_lock = threading.Lock()
        self._incoming = self._root / ".quarantine-incoming"
        for area in ("quarantine", "released"):
            path = self._root / area
            path.mkdir(parents=True, exist_ok=True)
            self._restrict(path, 0o700)
        self._index = QuarantineIndex(self._root, restrict=self._restrict)
        self._incoming.mkdir(exist_ok=True)
        self._restrict(self._incoming, 0o700)

    async def issue_upload(
        self, object_key: str, *, expires_at: datetime
    ) -> UploadGrant:
        self._path(object_key, "quarantine")
        with self._grant_lock:
            now = datetime.now(UTC)
            self._grants = {
                key: value
                for key, value in self._grants.items()
                if value.expires_at > now
            }
            existing = self._grants.get(object_key)
            if existing is not None:
                return existing
            grant = UploadGrant(
                object_key=object_key,
                token=token_urlsafe(32),
                expires_at=expires_at,
            )
            self._grants[object_key] = grant
            while len(self._grants) > self._maximum_grants:
                oldest = min(self._grants, key=lambda key: self._grants[key].expires_at)
                del self._grants[oldest]
            return grant

    async def write_quarantine(
        self,
        object_key: str,
        chunks: AsyncIterable[bytes],
        *,
        maximum_bytes: int,
    ) -> StoredObject:
        destination = self._path(object_key, "quarantine")
        self._ensure_no_symlinks(destination)
        digest = hashlib.sha256()
        observed = 0
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".upload-", dir=self._incoming
        )
        temporary = Path(temporary_name)
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
            await asyncio.to_thread(
                self._commit_quarantine, object_key, temporary, destination
            )
        except BaseException:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
            raise
        return StoredObject(
            size_bytes=observed,
            media_type="application/octet-stream",
            checksum=digest.hexdigest(),
        )

    def _commit_quarantine(
        self, object_key: str, temporary: Path, destination: Path
    ) -> None:
        with self._index.exclusive():
            destination.parent.mkdir(parents=True, exist_ok=True)
            self._restrict(destination.parent, 0o700)
            self._index.prepare(object_key)
            os.replace(temporary, destination)
            self._index.ready(object_key)
            self._restrict(destination, 0o600)

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
        self._ensure_no_symlinks(destination)
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
        self._ensure_no_symlinks(path)
        await asyncio.to_thread(self._delete_quarantine, object_key, path)
        await asyncio.to_thread(self._prune_empty_parents, path.parent, "quarantine")
        with self._grant_lock:
            self._grants.pop(object_key, None)

    def _delete_quarantine(self, object_key: str, path: Path) -> None:
        with self._index.exclusive():
            with contextlib.suppress(FileNotFoundError):
                path.unlink(True)
            self._index.remove(object_key)

    async def delete_released(self, object_key: str) -> None:
        path = self._path(object_key, "released")
        self._ensure_no_symlinks(path)
        with contextlib.suppress(FileNotFoundError):
            await asyncio.to_thread(path.unlink, True)

    def _path(self, object_key: str, area: str) -> Path:
        if not object_key or "\\" in object_key:
            raise ProductValidationFailed("The private object key is invalid.")
        parts = PurePath(object_key).parts
        if (
            not parts
            or parts[0] != area
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ProductValidationFailed("The private object key is invalid.")
        candidate = self._root.joinpath(*parts)
        return candidate

    def _existing(self, object_key: str, area: str) -> Path:
        path = self._path(object_key, area)
        self._ensure_no_symlinks(path)
        if area == "quarantine" and not path.is_file():
            staged = self._index.reconcile_root.joinpath(
                *PurePath(object_key).parts[1:]
            )
            self._ensure_no_symlinks(staged)
            if staged.is_file():
                return staged
        if not path.is_file():
            raise ProductDependencyUnavailable()
        return path

    def _ensure_no_symlinks(self, path: Path) -> None:
        current = self._root
        for component in path.relative_to(self._root).parts:
            current /= component
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(mode):
                raise ProductValidationFailed("Private object symlinks are forbidden.")

    @staticmethod
    async def _chunks(path: Path) -> AsyncIterator[bytes]:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            while chunk := await asyncio.to_thread(handle.read, 65_536):
                yield chunk

    @staticmethod
    def _metadata(path: Path) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            while chunk := handle.read(65_536):
                size += len(chunk)
                digest.update(chunk)
        return size, digest.hexdigest()

    def quarantine_keys(
        self, *, limit: int, after: str | None = None
    ) -> tuple[str, ...]:
        """Return an indexed stable page without traversing object directories."""

        return self._index.keys(limit=limit, after=after)

    def reconcile_quarantine_index(self, *, limit: int) -> int:
        """Recover pending writes and a bounded batch of legacy objects."""

        return self._index.reconcile(limit=limit)

    def _prune_empty_parents(self, directory: Path, area: str) -> None:
        boundary = self._root / area
        while directory != boundary:
            try:
                directory.rmdir()
            except OSError:
                break
            directory = directory.parent

    @staticmethod
    def _restrict(path: Path, mode: int) -> None:
        # Windows ACLs are configured by the containing local directory.
        with contextlib.suppress(OSError):
            path.chmod(mode)
