"""Framework-free environment and production configuration policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


@dataclass(frozen=True, slots=True)
class EnvironmentControls:
    """Primitive configuration values required by the environment policy."""

    production: bool
    product_max_file_bytes: int
    product_max_package_bytes: int
    login_rate_limit_per_source: int
    login_rate_limit_global: int
    product_clamav_host: str
    worker_health_required: bool
    allow_demo_users: bool
    session_cookie_secure: bool
    database_url: str
    camunda_rest_address: str
    camunda_auth_mode: str
    camunda_username_configured: bool
    camunda_password_configured: bool
    browser_origin: str
    trusted_origins: frozenset[str]
    allowed_hosts: frozenset[str]
    audit_key_configured: bool
    security_pseudonym_key_configured: bool
    audit_hmac_active_key_id: str
    audit_hmac_key_ids: frozenset[str]
    product_storage_path: Path
    request_matching_semantic_enabled: bool
    request_embedding_cache_path: Path


def normalise_browser_boundaries(
    web_origin: str,
    trusted_origins: frozenset[str],
    allowed_hosts: frozenset[str],
) -> tuple[str, frozenset[str], frozenset[str]]:
    """Canonicalise configured origins and derive their explicit hostnames."""
    origin = web_origin.rstrip("/")
    origins = frozenset(item.rstrip("/") for item in trusted_origins) | {origin}
    derived_hosts = {
        parsed.hostname
        for item in origins
        if (parsed := urlsplit(item)).hostname is not None
    }
    hosts = (
        frozenset(host.strip().lower() for host in allowed_hosts if host.strip())
        | derived_hosts
    )
    return origin, origins, hosts


def validate_environment_controls(controls: EnvironmentControls) -> None:
    """Reject unsafe combinations while preserving deterministic error order."""
    _validate_common_controls(controls)
    if not controls.production:
        return
    _validate_production_runtime(controls)
    _validate_production_dependencies(controls)
    _validate_production_browser_boundary(controls)
    _validate_production_keys(controls)
    _validate_production_storage(controls)


def _validate_common_controls(controls: EnvironmentControls) -> None:
    if controls.product_max_package_bytes < controls.product_max_file_bytes:
        raise ValueError(
            "the product package limit must be at least the per-file limit"
        )
    if controls.login_rate_limit_global < controls.login_rate_limit_per_source:
        raise ValueError("the global login rate limit must cover the per-source limit")
    if not controls.product_clamav_host.strip():
        raise ValueError("the ClamAV host must be non-empty")


def _validate_production_runtime(controls: EnvironmentControls) -> None:
    if not controls.worker_health_required:
        raise ValueError("the independent worker is required in production")
    if controls.allow_demo_users:
        raise ValueError("demo users must be disabled in production")
    if not controls.session_cookie_secure:
        raise ValueError("secure session cookies are required in production")


def _validate_production_dependencies(controls: EnvironmentControls) -> None:
    if not controls.database_url.startswith("postgresql+asyncpg://"):
        raise ValueError("production persistence must use PostgreSQL with asyncpg")
    if not _postgres_url_verifies_tls(controls.database_url):
        raise ValueError("production PostgreSQL must use ssl=verify-full")
    if not _is_https_url(controls.camunda_rest_address):
        raise ValueError("production Camunda endpoint must use HTTPS")
    if controls.camunda_auth_mode == "NONE":
        raise ValueError("Camunda authentication is required in production")
    if controls.camunda_auth_mode == "BASIC" and not (
        controls.camunda_username_configured and controls.camunda_password_configured
    ):
        raise ValueError("Camunda BASIC credentials must be non-empty")


def _validate_production_browser_boundary(controls: EnvironmentControls) -> None:
    if not controls.browser_origin.startswith("https://") or any(
        not item.startswith("https://") for item in controls.trusted_origins
    ):
        raise ValueError("production browser origins must use HTTPS")
    if not controls.allowed_hosts or any(
        "*" in host or "/" in host for host in controls.allowed_hosts
    ):
        raise ValueError("production allowed hosts must be explicit hostnames")


def _validate_production_keys(controls: EnvironmentControls) -> None:
    if not controls.audit_key_configured:
        raise ValueError("an audit HMAC key is required in production")
    if not controls.security_pseudonym_key_configured:
        raise ValueError("a security pseudonym key is required in production")
    if controls.audit_hmac_active_key_id not in controls.audit_hmac_key_ids:
        raise ValueError("the active audit HMAC key ID is absent from the keyring")


def _validate_production_storage(controls: EnvironmentControls) -> None:
    if not controls.product_storage_path.is_absolute():
        raise ValueError("production product storage must use an absolute private path")
    if (
        controls.request_matching_semantic_enabled
        and not controls.request_embedding_cache_path.is_absolute()
    ):
        raise ValueError(
            "the production request embedding cache must use an absolute path"
        )


def _is_https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


def _postgres_url_verifies_tls(value: str) -> bool:
    parameters = {
        key.lower(): item.lower()
        for key, values in parse_qs(urlsplit(value).query).items()
        for item in values
    }
    return parameters.get("ssl") == "verify-full"
