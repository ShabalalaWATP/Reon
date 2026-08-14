"""Focused branches for framework-free environment configuration policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from istari_service.config_environment_policy import (
    EnvironmentControls,
    normalise_browser_boundaries,
    validate_environment_controls,
)


def _production_controls(**updates: object) -> EnvironmentControls:
    values = {
        "production": True,
        "product_max_file_bytes": 10,
        "product_max_package_bytes": 20,
        "login_rate_limit_per_source": 10,
        "login_rate_limit_global": 20,
        "product_clamav_host": "clamav",
        "worker_health_required": True,
        "allow_demo_users": False,
        "session_cookie_secure": True,
        "database_url": "postgresql+asyncpg://service@db/app?ssl=verify-full",
        "camunda_rest_address": "https://workflow.example.test",
        "camunda_auth_mode": "BASIC",
        "camunda_username_configured": True,
        "camunda_password_configured": True,
        "browser_origin": "https://service.example.test",
        "trusted_origins": frozenset({"https://service.example.test"}),
        "allowed_hosts": frozenset({"service.example.test"}),
        "audit_key_configured": True,
        "security_pseudonym_key_configured": True,
        "audit_hmac_active_key_id": "active",
        "audit_hmac_key_ids": frozenset({"active"}),
        "product_storage_path": Path("C:/private/products"),
        "request_matching_semantic_enabled": True,
        "request_embedding_cache_path": Path("C:/private/model-cache"),
    }
    values.update(updates)
    return EnvironmentControls(**values)  # type: ignore[arg-type]


def test_browser_boundary_normalisation_derives_canonical_hosts() -> None:
    origin, trusted, hosts = normalise_browser_boundaries(
        "https://Service.Example.Test/",
        frozenset({"https://Staff.Example.Test/"}),
        frozenset({" API.EXAMPLE.TEST ", ""}),
    )

    assert origin == "https://Service.Example.Test"
    assert trusted == frozenset(
        {"https://Service.Example.Test", "https://Staff.Example.Test"}
    )
    assert hosts == frozenset(
        {"service.example.test", "staff.example.test", "api.example.test"}
    )


def test_production_camunda_https_requires_a_network_location() -> None:
    with pytest.raises(ValueError, match="Camunda endpoint must use HTTPS"):
        validate_environment_controls(
            _production_controls(camunda_rest_address="https:///missing-host")
        )


def test_disabled_semantic_matching_allows_relative_unused_cache() -> None:
    validate_environment_controls(
        _production_controls(
            request_matching_semantic_enabled=False,
            request_embedding_cache_path=Path("unused-relative-cache"),
        )
    )
