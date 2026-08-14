"""Password hashing and opaque browser-session primitives."""

from __future__ import annotations

from hashlib import sha256

from argon2 import PasswordHasher as ArgonPasswordHasher
from argon2 import Type
from argon2.exceptions import Argon2Error, InvalidHashError

DUMMY_HASH_INPUT = "local-unknown-account-input"


def hash_opaque_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def csrf_token_for_session(session_token: str) -> str:
    """Derive a stable, browser-readable CSRF secret from the opaque cookie value."""

    return sha256(f"istari-csrf-v1:{session_token}".encode()).hexdigest()


class PasswordHasher:
    """Argon2id wrapper kept replaceable for fast deterministic tests."""

    def __init__(
        self,
        *,
        time_cost: int = 3,
        memory_cost: int = 65_536,
        parallelism: int = 4,
    ) -> None:
        self._hasher = ArgonPasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, stored_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(stored_hash, password)
        except (Argon2Error, InvalidHashError):
            return False
