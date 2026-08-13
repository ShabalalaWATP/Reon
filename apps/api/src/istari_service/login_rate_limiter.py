"""Account-neutral source identification and login limiting contracts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from hmac import new as hmac_new
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address
from typing import Protocol

from fastapi import Request

Network = IPv4Network | IPv6Network


@dataclass(frozen=True, slots=True)
class LoginRateLimitPolicy:
    window_seconds: int
    per_source: int
    global_limit: int


@dataclass(frozen=True, slots=True)
class LoginRateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0
    first_denial: bool = False


class LoginRateLimitUnavailable(RuntimeError):
    """The shared budget could not be durably consumed within its deadline."""


class LoginAttemptLimiter(Protocol):
    """Persist an attempt before returning its decision to the caller."""

    async def consume(
        self,
        source_key: str,
        policy: LoginRateLimitPolicy,
    ) -> LoginRateLimitDecision: ...

    async def consume_scope_only(
        self, scope_key: str, policy: LoginRateLimitPolicy
    ) -> LoginRateLimitDecision: ...


def login_scope_key(scope: str, value: str, *, pseudonym_key: bytes) -> str:
    """Return a domain-separated, keyed lookup value for a limiter scope."""

    if len(pseudonym_key) < 32:
        raise ValueError("login pseudonym key must be at least 32 bytes")
    digest = hmac_new(
        pseudonym_key,
        f"istari-login-{scope}-v2:{value}".encode(),
        sha256,
    ).hexdigest()
    return f"{scope}:{digest}"


def credential_budget_key(username: str, *, pseudonym_key: bytes) -> str:
    return login_scope_key(
        "credential", username.strip().lower(), pseudonym_key=pseudonym_key
    )


def login_source_key(
    request: Request,
    trusted_proxies: tuple[Network, ...],
    *,
    pseudonym_key: bytes,
) -> str:
    """Return a non-reversible key without trusting caller-controlled headers."""

    peer = _address(request.client.host if request.client else None)
    source = peer
    if peer is not None and any(peer in network for network in trusted_proxies):
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded and "," not in forwarded:
            source = _address(forwarded.strip()) or peer
    canonical = source.compressed if source is not None else "unresolved"
    source_key = login_scope_key("source", canonical, pseudonym_key=pseudonym_key)
    # This is a content-free PostgreSQL lookup key, never an HTTP or HTML response.
    return source_key  # nosemgrep


def _address(value: str | None) -> IPv4Address | IPv6Address | None:
    if not value:
        return None
    try:
        parsed = ip_address(value)
    except ValueError:
        return None
    if isinstance(parsed, IPv6Address) and parsed.ipv4_mapped is not None:
        return parsed.ipv4_mapped
    return parsed
