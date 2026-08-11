"""Configuration validation and async database helper tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateTable

import istari_service.database as database_module
from istari_service.config import Environment, Settings, get_settings
from istari_service.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
    dispose_database,
)
from istari_service.models import Base, User, UserRole


def sqlite_settings(url: str = "sqlite+aiosqlite:///:memory:") -> Settings:
    return Settings(
        environment=Environment.TEST,
        database_url=url,
        allow_demo_users=False,
    )


def make_user(username: str) -> User:
    return User(
        username=username,
        email=username,
        display_name="Synthetic User",
        password_hash="$argon2id$synthetic",
        role=UserRole.REQUESTER,
        scope="Area A",
    )


def production_settings(**overrides: Any) -> Settings:
    product_storage_path = Path(tempfile.gettempdir()).resolve() / "istari-products"
    values: dict[str, Any] = {
        "environment": Environment.PROD,
        "database_url": "postgresql+asyncpg://service@db/istari?ssl=verify-full",
        "allow_demo_users": False,
        "session_cookie_secure": True,
        "camunda_auth_mode": "BASIC",
        "camunda_username": "service-client",
        "camunda_password": SecretStr("synthetic-password"),
        "camunda_rest_address": "https://workflow.example.test",
        "web_origin": "https://service.example.test",
        "trusted_origins": frozenset({"https://staff.example.test"}),
        "audit_hmac_key": SecretStr("a" * 32),
        "product_storage_path": str(product_storage_path),
        "request_embedding_cache_path": str(product_storage_path / "model-cache"),
        "worker_health_required": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_settings_normalise_origins_modes_and_aliases() -> None:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
        trusted_origins=(
            " http://requester.example.test/,https://staff.example.test/ "
        ),
        web_origin="http://localhost:5173/",
        session_cookie_samesite="STRICT",
        camunda_auth_mode="basic",
        CAMUNDA_BASE_URL="http://workflow.example.test/",
        product_allowed_external_domains=(
            " Products.Example.Test., files.example.test "
        ),
        trusted_proxy_cidrs="10.20.1.4/16,2001:db8::1/64",
    )
    assert settings.trusted_origins == frozenset(
        {
            "http://requester.example.test",
            "https://staff.example.test",
            "http://localhost:5173",
        }
    )
    assert settings.session_cookie_samesite == "strict"
    assert settings.camunda_auth_mode == "BASIC"
    assert settings.camunda_base_url == "http://workflow.example.test"
    assert settings.product_allowed_external_domains == frozenset(
        {"products.example.test", "files.example.test"}
    )
    assert settings.trusted_proxy_cidrs == frozenset({"10.20.0.0/16", "2001:db8::/64"})

    from_collection = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
        trusted_origins=frozenset({"http://one.example.test/"}),
    )
    assert from_collection.trusted_origins == frozenset(
        {"http://one.example.test", "http://localhost:5173"}
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"allow_demo_users": True}, "demo users"),
        ({"session_cookie_secure": False}, "secure session cookies"),
        ({"database_url": "sqlite+aiosqlite:///:memory:"}, "PostgreSQL"),
        (
            {"database_url": "postgresql+asyncpg://service@db/istari"},
            "ssl=verify-full",
        ),
        (
            {"database_url": ("postgresql+asyncpg://service@db/istari?ssl=disable")},
            "ssl=verify-full",
        ),
        (
            {"database_url": ("postgresql+asyncpg://service@db/istari?ssl=require")},
            "ssl=verify-full",
        ),
        ({"camunda_rest_address": "http://workflow.local"}, "must use HTTPS"),
        (
            {"allowed_hosts": frozenset({"*"})},
            "allowed hosts must be explicit",
        ),
        ({"audit_hmac_key": None}, "audit HMAC key is required"),
        (
            {"product_storage_path": ".local/product-storage"},
            "absolute private path",
        ),
        ({"audit_hmac_key": SecretStr("short")}, "at least 32 bytes"),
        ({"camunda_auth_mode": "NONE"}, "authentication is required"),
        ({"camunda_username": None}, "credentials must be non-empty"),
        ({"camunda_password": None}, "credentials must be non-empty"),
        ({"camunda_password": SecretStr("")}, "credentials must be non-empty"),
        ({"web_origin": "http://service.example.test"}, "origins must use HTTPS"),
        (
            {"trusted_origins": frozenset({"http://staff.example.test"})},
            "origins must use HTTPS",
        ),
    ],
)
def test_production_settings_reject_insecure_combinations(
    overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        production_settings(**overrides)


def test_settings_reject_invalid_enumerated_text_and_accept_secure_prod() -> None:
    with pytest.raises(ValidationError, match="SameSite"):
        sqlite_settings().model_copy(update={"session_cookie_samesite": "none"})
        Settings(
            environment=Environment.TEST,
            database_url="sqlite+aiosqlite:///:memory:",
            allow_demo_users=False,
            session_cookie_samesite="none",
        )
    with pytest.raises(ValidationError, match="NONE or BASIC"):
        Settings(
            environment=Environment.TEST,
            database_url="sqlite+aiosqlite:///:memory:",
            allow_demo_users=False,
            camunda_auth_mode="oauth",
        )
    assert production_settings().environment is Environment.PROD


def test_production_database_tls_parameter_reaches_asyncpg() -> None:
    settings = production_settings()
    _, connect_args = PGDialect_asyncpg().create_connect_args(
        make_url(settings.database_url)
    )

    assert connect_args["ssl"] == "verify-full"
    assert "sslmode" not in connect_args


def test_settings_reject_product_package_limit_below_file_limit() -> None:
    with pytest.raises(ValidationError, match="package limit"):
        Settings(
            environment=Environment.TEST,
            database_url="sqlite+aiosqlite:///:memory:",
            allow_demo_users=False,
            product_max_file_bytes=2_048,
            product_max_package_bytes=1_024,
        )


def test_settings_reject_invalid_login_security_configuration() -> None:
    with pytest.raises(ValidationError, match="trusted proxy CIDRs"):
        Settings(trusted_proxy_cidrs="not-a-network")
    with pytest.raises(ValidationError, match="global login rate limit"):
        Settings(
            login_rate_limit_per_source=20,
            login_rate_limit_global=10,
        )
    with pytest.raises(ValidationError, match="ClamAV host"):
        Settings(
            environment=Environment.TEST,
            database_url="sqlite+aiosqlite:///:memory:",
            allow_demo_users=False,
            product_clamav_host=" ",
        )


def test_get_settings_is_cached_and_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("ALLOW_DEMO_USERS", "false")
    first = get_settings()
    assert first is get_settings()
    assert first.environment is Environment.TEST
    get_settings.cache_clear()


def test_engine_builder_selects_pool_options_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    sentinel = object()

    def fake_create(url: str, **kwargs: object) -> object:
        calls.append((url, kwargs))
        return sentinel

    monkeypatch.setattr(database_module, "create_async_engine", fake_create)
    memory = sqlite_settings()
    assert create_database_engine(memory) is sentinel
    assert calls[-1][1]["poolclass"] is database_module.StaticPool
    assert calls[-1][1]["connect_args"] == {"check_same_thread": False}

    assert (
        create_database_engine(sqlite_settings("sqlite+aiosqlite:///test.db"))
        is sentinel
    )
    assert "poolclass" not in calls[-1][1]

    postgres = Settings(
        environment=Environment.TEST,
        database_url="postgresql+asyncpg://service@localhost/istari",
        database_pool_size=7,
        database_max_overflow=9,
        allow_demo_users=False,
    )
    monkeypatch.setattr(database_module, "get_settings", lambda: postgres)
    assert create_database_engine() is sentinel
    assert calls[-1][1]["pool_size"] == 7
    assert calls[-1][1]["max_overflow"] == 9


@pytest.mark.asyncio
async def test_schema_creation_and_disposal() -> None:
    engine = create_database_engine(sqlite_settings())
    await create_schema(engine)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        session.add(make_user("scoped@example.test"))
    async with factory() as session:
        assert await session.scalar(select(func.count(User.id))) == 1
    await dispose_database(engine)


def test_metadata_compiles_for_supported_database_dialects() -> None:
    for dialect in (postgresql.dialect(), sqlite.dialect()):
        statements = [
            str(CreateTable(table).compile(dialect=dialect))
            for table in Base.metadata.sorted_tables
        ]
        assert len(statements) == len(Base.metadata.tables)
        assert len(statements) >= 40
        assert all("CREATE TABLE" in statement for statement in statements)
