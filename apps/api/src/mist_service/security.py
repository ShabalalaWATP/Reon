"""Cookie-session request protections."""

from __future__ import annotations

from secrets import compare_digest

from mist_service.auth_service import hash_opaque_token
from mist_service.domain import SessionRecord
from mist_service.errors import CsrfFailed


def require_csrf(
    session: SessionRecord,
    submitted_token: str | None,
    origin: str | None,
    trusted_origins: frozenset[str],
) -> None:
    """Validate both the trusted browser origin and per-session CSRF secret."""

    if origin is None or origin.rstrip("/") not in trusted_origins:
        raise CsrfFailed()
    if submitted_token is None or not compare_digest(
        hash_opaque_token(submitted_token),
        session.csrf_token_hash,
    ):
        raise CsrfFailed()
