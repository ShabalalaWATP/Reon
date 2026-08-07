"""Validated application configuration sourced from environment variables."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any, Self
from urllib.parse import parse_qs, urlsplit

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PROD = "prod"


def _is_https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


def _postgres_url_requires_tls(value: str) -> bool:
    parameters = {
        key.lower(): item.lower()
        for key, values in parse_qs(urlsplit(value).query).items()
        for item in values
    }
    accepted = {"1", "true", "require", "verify-ca", "verify-full"}
    return parameters.get("ssl") in accepted or parameters.get("sslmode") in accepted


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
    max_request_body_bytes: int = Field(
        default=1_048_576,
        ge=1_024,
        le=10_485_760,
    )
    audit_hmac_key: SecretStr | None = None

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

    @model_validator(mode="after")
    def validate_environment_controls(self) -> Self:
        origin = self.web_origin.rstrip("/")
        self.trusted_origins = frozenset(
            item.rstrip("/") for item in self.trusted_origins
        ) | {origin}
        derived_hosts = {
            parsed.hostname
            for item in self.trusted_origins
            if (parsed := urlsplit(item)).hostname is not None
        }
        self.allowed_hosts = (
            frozenset(
                host.strip().lower() for host in self.allowed_hosts if host.strip()
            )
            | derived_hosts
        )
        if self.environment is Environment.PROD:
            if self.allow_demo_users:
                raise ValueError("demo users must be disabled in production")
            if not self.session_cookie_secure:
                raise ValueError("secure session cookies are required in production")
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError(
                    "production persistence must use PostgreSQL with asyncpg"
                )
            if not _postgres_url_requires_tls(self.database_url):
                raise ValueError("production PostgreSQL must require TLS")
            if not _is_https_url(self.camunda_rest_address):
                raise ValueError("production Camunda endpoint must use HTTPS")
            if self.camunda_auth_mode == "NONE":
                raise ValueError("Camunda authentication is required in production")
            if self.camunda_auth_mode == "BASIC" and (
                not self.camunda_username
                or not self.camunda_password
                or not self.camunda_password.get_secret_value()
            ):
                raise ValueError("Camunda BASIC credentials must be non-empty")
            if not origin.startswith("https://") or any(
                not item.startswith("https://") for item in self.trusted_origins
            ):
                raise ValueError("production browser origins must use HTTPS")
            if not self.allowed_hosts or any(
                "*" in host or "/" in host for host in self.allowed_hosts
            ):
                raise ValueError("production allowed hosts must be explicit hostnames")
            if self.audit_hmac_key is None:
                raise ValueError("an audit HMAC key is required in production")
        return self

    @property
    def audit_hmac_key_bytes(self) -> bytes | None:
        if self.audit_hmac_key is None:
            return None
        return self.audit_hmac_key.get_secret_value().encode("utf-8")

    @property
    def camunda_base_url(self) -> str:
        return self.camunda_rest_address.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
