"""Validated application configuration sourced from environment variables."""

from __future__ import annotations

import json
from enum import StrEnum
from functools import lru_cache
from ipaddress import IPv4Network, IPv6Network, ip_network
from pathlib import Path
from typing import Annotated, Any, Self

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from istari_service.config_environment_policy import (
    EnvironmentControls,
    normalise_browser_boundaries,
    validate_environment_controls,
)


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PROD = "prod"


class Settings(BaseSettings):
    """Process settings with secure production invariants."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    environment: Environment = Environment.LOCAL
    database_url: str = (
        "postgresql+asyncpg://istari_service@localhost:5432/istari_service"
    )
    database_pool_size: int = Field(default=20, ge=1, le=50)
    database_max_overflow: int = Field(default=30, ge=0, le=50)
    trusted_origins: Annotated[frozenset[str], NoDecode] = Field(
        default_factory=lambda: frozenset({"http://localhost:5173"})
    )
    web_origin: str = "http://localhost:5173"
    allowed_hosts: Annotated[frozenset[str], NoDecode] = Field(
        default_factory=frozenset
    )

    session_cookie_name: str = "istari_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_ttl_seconds: int = Field(default=28_800, ge=300, le=86_400)
    session_idle_seconds: int = Field(default=3_600, ge=60, le=86_400)
    admin_elevation_seconds: int = Field(default=300, ge=60, le=900)
    login_rate_limit_window_seconds: int = Field(default=60, ge=10, le=3_600)
    login_rate_limit_per_source: int = Field(default=30, ge=1, le=1_000)
    login_rate_limit_global: int = Field(default=300, ge=1, le=10_000)
    login_rate_limit_timeout_seconds: float = Field(default=3.0, ge=0.25, le=10)
    login_hash_concurrency: int = Field(default=2, ge=1, le=16)
    trusted_proxy_cidrs: Annotated[frozenset[str], NoDecode] = Field(
        default_factory=frozenset
    )
    max_request_body_bytes: int = Field(
        default=1_048_576,
        ge=1_024,
        le=10_485_760,
    )
    product_storage_path: Path = Path(".local/product-storage")
    product_allowed_external_domains: Annotated[frozenset[str], NoDecode] = Field(
        default_factory=frozenset
    )
    product_upload_ttl_seconds: int = Field(default=600, ge=60, le=3_600)
    product_clamav_host: str = "clamav"
    product_clamav_port: int = Field(default=3_310, ge=1, le=65_535)
    product_clamav_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    product_max_file_bytes: int = Field(
        default=25 * 1024 * 1024,
        ge=1_024,
        le=25 * 1024 * 1024,
    )
    product_max_package_bytes: int = Field(
        default=100 * 1024 * 1024,
        ge=1_024,
        le=100 * 1024 * 1024,
    )
    audit_hmac_key: SecretStr | None = None
    audit_hmac_active_key_id: str = "legacy"
    audit_hmac_keyring: SecretStr | None = None
    security_pseudonym_key: SecretStr | None = None
    security_pseudonym_key_id: str = "stable-v1"
    maintenance_operator_subject: str | None = None
    maintenance_disposal_authority: str | None = None
    maintenance_legal_hold_authority: str | None = None
    maintenance_database_url: str | None = None

    camunda_rest_address: str = Field(
        default="http://localhost:8080",
        validation_alias=AliasChoices("CAMUNDA_REST_ADDRESS", "CAMUNDA_BASE_URL"),
    )
    camunda_process_id: str = "service-request-v1"
    camunda_auth_mode: str = "NONE"
    camunda_username: str | None = None
    camunda_password: SecretStr | None = None

    allow_demo_users: bool = True
    demo_user_password: SecretStr | None = None
    action_workspace_enabled: bool = False
    notifications_enabled: bool = False
    managed_products_enabled: bool = False
    managed_file_uploads_enabled: bool = True
    configuration_admin_enabled: bool = False
    planning_evolution_enabled: bool = False
    statistics_evolution_enabled: bool = False
    worker_health_required: bool = False
    worker_interval_seconds: float = Field(default=0.5, ge=0.05, le=30)
    worker_lease_seconds: float = Field(default=30, ge=5, le=300)
    worker_heartbeat_stale_seconds: float = Field(default=10, ge=2, le=600)
    request_matching_semantic_enabled: bool = True
    request_embedding_model: str = "BAAI/bge-small-en-v1.5"
    request_embedding_cache_path: Path = Path(".local/request-embedding-cache")
    request_embedding_threads: int = Field(default=2, ge=1, le=8)
    request_embedding_batch_size: int = Field(default=8, ge=1, le=32)

    @field_validator("trusted_origins", mode="before")
    @classmethod
    def parse_trusted_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return frozenset(
                item.strip().rstrip("/") for item in value.split(",") if item.strip()
            )
        return value

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: Any) -> Any:
        if isinstance(value, str):
            return frozenset(
                item.strip().lower() for item in value.split(",") if item.strip()
            )
        return value

    @field_validator("trusted_proxy_cidrs", mode="before")
    @classmethod
    def parse_trusted_proxy_cidrs(cls, value: Any) -> Any:
        values = value.split(",") if isinstance(value, str) else value
        if values is None:
            return frozenset()
        try:
            return frozenset(
                str(ip_network(str(item).strip(), strict=False))
                for item in values
                if str(item).strip()
            )
        except ValueError as error:
            raise ValueError("trusted proxy CIDRs must be valid IP networks") from error

    @field_validator("product_allowed_external_domains", mode="before")
    @classmethod
    def parse_product_domains(cls, value: Any) -> Any:
        if isinstance(value, str):
            return frozenset(
                item.strip().lower().rstrip(".")
                for item in value.split(",")
                if item.strip()
            )
        return value

    @field_validator("session_cookie_samesite")
    @classmethod
    def validate_samesite(cls, value: str) -> str:
        normalised = value.lower()
        if normalised not in {"lax", "strict"}:
            raise ValueError("session cookie SameSite must be 'lax' or 'strict'")
        return normalised

    @field_validator("camunda_auth_mode")
    @classmethod
    def validate_camunda_auth_mode(cls, value: str) -> str:
        normalised = value.upper()
        if normalised not in {"NONE", "BASIC"}:
            raise ValueError("Camunda authentication must be NONE or BASIC")
        return normalised

    @field_validator("audit_hmac_key")
    @classmethod
    def validate_audit_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("audit HMAC key must contain at least 32 bytes")
        return value

    @field_validator("security_pseudonym_key")
    @classmethod
    def validate_security_pseudonym_key(
        cls, value: SecretStr | None
    ) -> SecretStr | None:
        if value is not None and len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("security pseudonym key must contain at least 32 bytes")
        return value

    @field_validator("audit_hmac_active_key_id", "security_pseudonym_key_id")
    @classmethod
    def validate_audit_key_id(cls, value: str) -> str:
        if (
            not value
            or len(value) > 64
            or not all(c.isalnum() or c in "._-" for c in value)
        ):
            raise ValueError("audit HMAC key ID must be a bounded safe identifier")
        return value

    @field_validator("audit_hmac_keyring")
    @classmethod
    def validate_audit_keyring(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        try:
            parsed = json.loads(value.get_secret_value())
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("audit HMAC keyring must be a JSON object") from error
        if not isinstance(parsed, dict) or not parsed:
            raise ValueError("audit HMAC keyring must contain at least one key")
        for key_id, key in parsed.items():
            cls.validate_audit_key_id(str(key_id))
            if not isinstance(key, str) or len(key.encode("utf-8")) < 32:
                raise ValueError("every audit HMAC key must contain at least 32 bytes")
        return value

    @model_validator(mode="after")
    def validate_environment_controls(self) -> Self:
        origin, self.trusted_origins, self.allowed_hosts = normalise_browser_boundaries(
            self.web_origin,
            self.trusted_origins,
            self.allowed_hosts,
        )
        password = self.camunda_password
        validate_environment_controls(
            EnvironmentControls(
                production=self.environment is Environment.PROD,
                product_max_file_bytes=self.product_max_file_bytes,
                product_max_package_bytes=self.product_max_package_bytes,
                login_rate_limit_per_source=self.login_rate_limit_per_source,
                login_rate_limit_global=self.login_rate_limit_global,
                product_clamav_host=self.product_clamav_host,
                worker_health_required=self.worker_health_required,
                allow_demo_users=self.allow_demo_users,
                session_cookie_secure=self.session_cookie_secure,
                database_url=self.database_url,
                camunda_rest_address=self.camunda_rest_address,
                camunda_auth_mode=self.camunda_auth_mode,
                camunda_username_configured=bool(self.camunda_username),
                camunda_password_configured=bool(
                    password and password.get_secret_value()
                ),
                browser_origin=origin,
                trusted_origins=self.trusted_origins,
                allowed_hosts=self.allowed_hosts,
                audit_key_configured=(
                    self.audit_hmac_key is not None
                    or self.audit_hmac_keyring is not None
                ),
                security_pseudonym_key_configured=(
                    self.security_pseudonym_key is not None
                ),
                audit_hmac_active_key_id=self.audit_hmac_active_key_id,
                audit_hmac_key_ids=frozenset(self.audit_hmac_keys),
                product_storage_path=self.product_storage_path,
                request_matching_semantic_enabled=(
                    self.request_matching_semantic_enabled
                ),
                request_embedding_cache_path=self.request_embedding_cache_path,
            )
        )
        return self

    @property
    def audit_hmac_key_bytes(self) -> bytes | None:
        return self.audit_hmac_keys.get(self.audit_hmac_active_key_id)

    @property
    def audit_hmac_keys(self) -> dict[str, bytes]:
        if self.audit_hmac_keyring is not None:
            parsed = json.loads(self.audit_hmac_keyring.get_secret_value())
            return {
                str(key): str(value).encode("utf-8") for key, value in parsed.items()
            }
        if self.audit_hmac_key is None:
            return {}
        material = self.audit_hmac_key.get_secret_value().encode("utf-8")
        return {self.audit_hmac_active_key_id: material}

    @property
    def camunda_base_url(self) -> str:
        return self.camunda_rest_address.rstrip("/")

    @property
    def trusted_proxy_networks(self) -> tuple[IPv4Network | IPv6Network, ...]:
        return tuple(
            ip_network(value, strict=False)
            for value in sorted(self.trusted_proxy_cidrs)
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
