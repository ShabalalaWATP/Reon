"""Durable bounded index and recovery for local quarantine objects."""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, BinaryIO, cast


class QuarantineIndex:
    def __init__(self, root: Path, *, restrict: Callable[[Path, int], None]) -> None:
        self.root = root
        self.quarantine = root / "quarantine"
        self.reconcile_root = root / ".quarantine-reconcile"
        self.path = root / ".quarantine-index.sqlite3"
        self._lock = threading.RLock()
        self._lock_path = root / ".quarantine-index.lock"
        if not self._lock_path.exists():
            self._lock_path.write_bytes(b"0")
        self.reconcile_root.mkdir(exist_ok=True)
        with os.scandir(self.quarantine) as entries:
            legacy_exists = any(not entry.name.startswith(".") for entry in entries)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS quarantine_objects "
                "(object_key TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'READY')"
            )
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(quarantine_objects)")
            }
            if "state" not in columns:
                connection.execute(
                    "ALTER TABLE quarantine_objects ADD COLUMN state TEXT "
                    "NOT NULL DEFAULT 'READY'"
                )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS quarantine_index_state "
                "(id INTEGER PRIMARY KEY CHECK (id = 1), "
                "legacy_complete INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS quarantine_legacy_roots "
                "(root_name TEXT PRIMARY KEY)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO quarantine_index_state VALUES (1, ?)",
                (0 if legacy_exists else 1,),
            )
        restrict(self.path, 0o600)

    def keys(self, *, limit: int, after: str | None) -> tuple[str, ...]:
        if limit < 1:
            raise ValueError("quarantine enumeration limit must be positive")
        with closing(sqlite3.connect(self.path)) as connection:
            if after is None:
                rows = connection.execute(
                    "SELECT object_key FROM quarantine_objects "
                    "WHERE state = 'READY' ORDER BY object_key LIMIT ?",
                    (limit,),
                )
            else:
                rows = connection.execute(
                    "SELECT object_key FROM quarantine_objects "
                    "WHERE state = 'READY' AND object_key > ? "
                    "ORDER BY object_key LIMIT ?",
                    (after, limit),
                )
            return tuple(str(row[0]) for row in rows)

    def prepare(self, object_key: str) -> None:
        with self._lock:
            self._set_state(object_key, "PENDING")

    def ready(self, object_key: str) -> None:
        with self._lock:
            self._set_state(object_key, "READY")

    def remove(self, object_key: str) -> None:
        with self._lock, closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "DELETE FROM quarantine_objects WHERE object_key = ?", (object_key,)
            )

    def reconcile(self, *, limit: int) -> int:
        if limit < 1:
            raise ValueError("quarantine reconciliation limit must be positive")
        with self.exclusive():
            recovered = self._recover_pending(limit)
            if recovered == limit:
                return recovered
            while recovered < limit:
                self._stage_one_legacy_root()
                advanced = self._recover_legacy(limit - recovered)
                recovered += advanced
                if advanced == 0:
                    break
            return recovered

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        """Serialise filesystem/index transitions across processes."""

        with self._lock, self._lock_path.open("a+b") as handle:
            self._lock_file(handle)
            try:
                yield
            finally:
                self._unlock_file(handle)

    @staticmethod
    def _lock_file(handle: BinaryIO) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            module = cast(Any, fcntl)
            module.flock(handle.fileno(), module.LOCK_EX)

    @staticmethod
    def _unlock_file(handle: BinaryIO) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            module = cast(Any, fcntl)
            module.flock(handle.fileno(), module.LOCK_UN)

    def _recover_pending(self, limit: int) -> int:
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                "SELECT object_key FROM quarantine_objects WHERE state = 'PENDING' "
                "ORDER BY object_key LIMIT ?",
                (limit,),
            ).fetchall()
        recovered = 0
        for (object_key,) in rows:
            path = self.root / str(object_key)
            if path.is_file():
                self.ready(str(object_key))
                recovered += 1
            else:
                self.remove(str(object_key))
        return recovered

    def _stage_one_legacy_root(self) -> None:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            complete = connection.execute(
                "SELECT legacy_complete FROM quarantine_index_state WHERE id = 1"
            ).fetchone()
            if complete and complete[0]:
                return
            with os.scandir(self.quarantine) as entries:
                entry = next(
                    (
                        item
                        for item in entries
                        if not item.name.startswith(".")
                        and not self._legacy_root_seen(item.name)
                    ),
                    None,
                )
            if entry is not None:
                destination = self.reconcile_root / entry.name
                if not destination.exists():
                    os.replace(entry.path, destination)
                connection.execute(
                    "INSERT OR IGNORE INTO quarantine_legacy_roots VALUES (?)",
                    (entry.name,),
                )
                return
            connection.execute(
                "UPDATE quarantine_index_state SET legacy_complete = 1 WHERE id = 1"
            )

    def _legacy_root_seen(self, root_name: str) -> bool:
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                "SELECT 1 FROM quarantine_legacy_roots WHERE root_name = ?",
                (root_name,),
            ).fetchone()
            return row is not None

    def _recover_legacy(self, limit: int) -> int:
        recovered = 0
        pending = [self.reconcile_root]
        while pending and recovered < limit:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        relative = Path(entry.path).relative_to(self.reconcile_root)
                        key = f"quarantine/{relative.as_posix()}"
                        destination = self.root / key
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        if self._is_ready(key):
                            os.replace(entry.path, destination)
                        else:
                            self.prepare(key)
                            os.replace(entry.path, destination)
                            self.ready(key)
                            recovered += 1
                        if recovered == limit:
                            break
            self._prune(directory, self.reconcile_root)
        return recovered

    def _is_ready(self, object_key: str) -> bool:
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                "SELECT 1 FROM quarantine_objects "
                "WHERE object_key = ? AND state = 'READY'",
                (object_key,),
            ).fetchone()
            return row is not None

    def _set_state(self, object_key: str, state: str) -> None:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "INSERT INTO quarantine_objects (object_key, state) VALUES (?, ?) "
                "ON CONFLICT(object_key) DO UPDATE SET state = excluded.state",
                (object_key, state),
            )

    @staticmethod
    def _prune(directory: Path, boundary: Path) -> None:
        while directory != boundary:
            try:
                directory.rmdir()
            except OSError:
                break
            directory = directory.parent
