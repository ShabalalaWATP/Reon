"""Lifecycle, readiness and bounded maintenance branch coverage."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import Response
from pydantic import SecretStr
from sqlalchemy.exc import SQLAlchemyError

import mist_service.health_composition as health_composition
import mist_service.main as main_module
from mist_service.auth_service import PasswordHasher
from mist_service.config import Environment, Settings
from mist_service.errors import AuthenticationFailed, ServiceError
from mist_service.main import create_app
from mist_service.routers.health import health, readiness
from mist_service.workflow.fake import FakeWorkflowEngine
from mist_service.workflow_client import camunda_client_configuration


class FastHasher(PasswordHasher):
    def __init__(self) -> None:
        pass

    def hash(self, password: str) -> str:
        return f"test-hash:{len(password)}"


def disable_organisation_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_seed(_session: object) -> int:
        return 0

    monkeypatch.setattr(main_module, "seed_organisation_units", no_seed)
    monkeypatch.setattr(main_module, "seed_baseline_configuration", no_seed)
    monkeypatch.setattr(main_module, "restore_active_configuration_projection", no_seed)
    monkeypatch.setattr(main_module, "initialise_admin_identity_sequence", no_seed)
    monkeypatch.setattr(main_module, "initialise_admin_audit_anchor", no_seed)
    monkeypatch.setattr(main_module, "initialise_platform_classification", no_seed)


def make_settings(**updates: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": Environment.TEST,
        "database_url": "sqlite+aiosqlite:///:memory:",
        "allow_demo_users": False,
        "web_origin": "http://test.local",
        "trusted_origins": frozenset({"http://test.local"}),
    }
    values.update(updates)
    return Settings(**values)


class SessionContext:
    def __init__(self) -> None:
        self.entered = 0

    async def __aenter__(self) -> SessionContext:
        self.entered += 1
        return self

    async def __aexit__(self, *_args: object) -> None:
        self.entered -= 1

    def begin(self) -> SessionContext:
        return self


class SessionFactoryDouble:
    def __init__(self) -> None:
        self.sessions: list[SessionContext] = []

    def __call__(self) -> SessionContext:
        session = SessionContext()
        self.sessions.append(session)
        return session


def test_client_configuration_handles_paths_basic_auth_and_rejects_unknown() -> None:
    none_configuration = camunda_client_configuration(
        make_settings(camunda_rest_address="http://workflow.local/")
    )
    assert none_configuration == {
        "CAMUNDA_REST_ADDRESS": "http://workflow.local/v2",
        "CAMUNDA_AUTH_STRATEGY": "NONE",
        "CAMUNDA_SDK_LOG_LEVEL": "warn",
    }

    basic = make_settings(
        camunda_rest_address="https://workflow.example.test/v2",
        camunda_auth_mode="basic",
        camunda_username="synthetic-client",
        camunda_password=SecretStr("synthetic-secret"),
    )
    assert camunda_client_configuration(basic) == {
        "CAMUNDA_REST_ADDRESS": "https://workflow.example.test/v2",
        "CAMUNDA_AUTH_STRATEGY": "BASIC",
        "CAMUNDA_SDK_LOG_LEVEL": "warn",
        "CAMUNDA_BASIC_AUTH_USERNAME": "synthetic-client",
        "CAMUNDA_BASIC_AUTH_PASSWORD": "synthetic-secret",
    }

    missing_credentials = make_settings(camunda_auth_mode="BASIC")
    configuration = camunda_client_configuration(missing_credentials)
    assert configuration["CAMUNDA_BASIC_AUTH_USERNAME"] == ""
    assert configuration["CAMUNDA_BASIC_AUTH_PASSWORD"] == ""

    invalid = basic.model_copy(update={"camunda_auth_mode": "oauth"})
    with pytest.raises(ValueError, match="only NONE or BASIC"):
        camunda_client_configuration(invalid)


def test_create_app_uses_default_composition_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = make_settings()
    sessions = object()
    hasher = FastHasher()
    monkeypatch.setattr(main_module, "get_settings", lambda: configured)
    monkeypatch.setattr(main_module, "SessionFactory", sessions)
    monkeypatch.setattr(main_module, "PasswordHasher", lambda: hasher)

    application = create_app()

    assert application.state.settings is configured
    assert application.state.session_factory is sessions
    assert application.state.password_hasher is hasher
    assert application.state.dummy_password_hash.startswith("test-hash:")


def test_production_disables_interactive_api_schema_surfaces(tmp_path: Path) -> None:
    application = create_app(
        settings=Settings(
            environment=Environment.PROD,
            database_url=("postgresql+asyncpg://service@db/mist?ssl=verify-full"),
            allow_demo_users=False,
            session_cookie_secure=True,
            web_origin="https://staff.example.test",
            trusted_origins=frozenset({"https://staff.example.test"}),
            allowed_hosts=frozenset({"api.example.test"}),
            camunda_rest_address="https://workflow.example.test",
            camunda_auth_mode="BASIC",
            camunda_username="synthetic-client",
            camunda_password=SecretStr("synthetic-secret"),
            audit_hmac_key=SecretStr("a" * 32),
            security_pseudonym_key=SecretStr("s" * 32),
            product_storage_path=str(tmp_path / "mist-products"),
            request_embedding_cache_path=str(tmp_path / "model-cache"),
            worker_health_required=True,
        ),
        workflow_engine=FakeWorkflowEngine(),
    )

    assert application.openapi_url is None
    assert application.docs_url is None
    assert application.redoc_url is None
    route_paths = {getattr(route, "path", None) for route in application.routes}
    assert not {"/openapi.json", "/docs", "/redoc"} & route_paths


def test_health_routes_are_not_published_in_local_openapi() -> None:
    application = create_app(
        settings=make_settings(),
        workflow_engine=FakeWorkflowEngine(),
    )
    paths = application.openapi()["paths"]
    assert "/health" not in paths
    assert "/ready" not in paths


@pytest.mark.asyncio
@pytest.mark.parametrize("demo_password", [None, SecretStr("synthetic-demo-secret")])
async def test_lifespan_passes_optional_demo_password_to_seeder(
    monkeypatch: pytest.MonkeyPatch,
    demo_password: SecretStr | None,
) -> None:
    disable_organisation_seed(monkeypatch)
    calls: list[dict[str, object]] = []

    async def fake_seed(_session: object, _hasher: object, **kwargs: object) -> int:
        calls.append(kwargs)
        return 16

    monkeypatch.setattr(main_module, "seed_demo_users", fake_seed)
    sessions = SessionFactoryDouble()
    application = create_app(
        settings=make_settings(
            allow_demo_users=True,
            demo_user_password=demo_password,
        ),
        session_factory=cast(Any, sessions),
        workflow_engine=FakeWorkflowEngine(),
        password_hasher=FastHasher(),
    )

    async with application.router.lifespan_context(application):
        assert application.state.workflow_engine is not None

    expected_password = (
        demo_password.get_secret_value() if demo_password is not None else None
    )
    assert calls == [
        {
            "environment": "test",
            "enabled": True,
            "shared_password": expected_password,
            "ensure_organisation": False,
        }
    ]
    assert sessions.sessions[0].entered == 0


@pytest.mark.asyncio
async def test_lifespan_creates_and_closes_camunda_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disable_organisation_seed(monkeypatch)
    events: list[object] = []
    engine = FakeWorkflowEngine()

    @asynccontextmanager
    async def runtime(configured: Settings) -> AsyncIterator[FakeWorkflowEngine]:
        events.append(("entered", configured.camunda_base_url))
        try:
            yield engine
        finally:
            events.append("exited")

    application = create_app(
        settings=make_settings(),
        session_factory=cast(Any, SessionFactoryDouble()),
        password_hasher=FastHasher(),
        workflow_runtime_factory=runtime,
    )

    async with application.router.lifespan_context(application):
        assert application.state.workflow_engine is engine

    assert events == [("entered", "http://localhost:8080"), "exited"]


@pytest.mark.asyncio
async def test_lifespan_never_hosts_the_independent_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disable_organisation_seed(monkeypatch)
    application = create_app(
        settings=make_settings(),
        session_factory=cast(Any, SessionFactoryDouble()),
        workflow_engine=FakeWorkflowEngine(),
        password_hasher=FastHasher(),
    )

    async with application.router.lifespan_context(application):
        assert not hasattr(application.state, "workflow_maintenance_health")


@pytest.mark.asyncio
async def test_registered_service_error_handler_uses_stable_envelope() -> None:
    application = create_app(
        settings=make_settings(),
        workflow_engine=FakeWorkflowEngine(),
        password_hasher=FastHasher(),
    )
    handler = application.exception_handlers[ServiceError]
    request = cast(Any, type("Request", (), {"method": "GET"})())
    response = await handler(request, AuthenticationFailed())

    assert response.status_code == 401
    assert json.loads(response.body) == {
        "detail": {
            "code": "AUTHENTICATION_FAILED",
            "message": "Unable to sign in with those credentials.",
        }
    }


class HealthSessionDouble:
    def __init__(self, database_ok: bool) -> None:
        self.database_ok = database_ok
        self.rollbacks = 0

    async def execute(self, _statement: object) -> None:
        if not self.database_ok:
            raise SQLAlchemyError("synthetic database outage")

    async def rollback(self) -> None:
        self.rollbacks += 1


class HealthEngineDouble:
    def __init__(self, reachable: bool) -> None:
        self.reachable = reachable

    async def is_reachable(self) -> bool:
        return self.reachable


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("database_ok", "workflow_ok", "expected_status"),
    [(True, True, 200), (False, True, 503), (True, False, 503)],
)
async def test_health_and_readiness_cover_dependency_combinations(
    database_ok: bool,
    workflow_ok: bool,
    expected_status: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def configuration_ready(_session: object) -> bool:
        return True

    monkeypatch.setattr(
        health_composition,
        "configuration_runtime_is_ready",
        configuration_ready,
    )
    response = Response()
    session = HealthSessionDouble(database_ok)
    result = await readiness(
        response,
        cast(Any, session),
        cast(Any, HealthEngineDouble(workflow_ok)),
        make_settings(worker_health_required=False),
    )

    assert await health() == {"status": "ok"}
    assert response.status_code == expected_status
    assert result.status == ("ready" if expected_status == 200 else "not_ready")
    assert result.checks.database == ("ok" if database_ok else "unavailable")
    assert result.checks.workflow == ("ok" if workflow_ok else "unavailable")
    assert result.checks.configuration == ("ok" if database_ok else "unavailable")
    assert result.checks.maintenance == "disabled"
    assert session.rollbacks == (0 if database_ok else 1)
