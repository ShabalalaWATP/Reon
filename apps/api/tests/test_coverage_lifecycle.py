"""Lifecycle, readiness and bounded maintenance branch coverage."""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

import pytest
from fastapi import Response
from pydantic import SecretStr
from sqlalchemy.exc import SQLAlchemyError

import istari_service.main as main_module
from istari_service.auth_service import PasswordHasher
from istari_service.config import Environment, Settings
from istari_service.errors import AuthenticationFailed, ServiceError
from istari_service.main import _client_configuration, create_app
from istari_service.routers.health import health, readiness
from istari_service.workflow.fake import FakeWorkflowEngine


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
    monkeypatch.setattr(main_module, "initialise_admin_identity_sequence", no_seed)
    monkeypatch.setattr(main_module, "initialise_admin_audit_anchor", no_seed)


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
    none_configuration = _client_configuration(
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
    assert _client_configuration(basic) == {
        "CAMUNDA_REST_ADDRESS": "https://workflow.example.test/v2",
        "CAMUNDA_AUTH_STRATEGY": "BASIC",
        "CAMUNDA_SDK_LOG_LEVEL": "warn",
        "CAMUNDA_BASIC_AUTH_USERNAME": "synthetic-client",
        "CAMUNDA_BASIC_AUTH_PASSWORD": "synthetic-secret",
    }

    missing_credentials = make_settings(camunda_auth_mode="BASIC")
    configuration = _client_configuration(missing_credentials)
    assert configuration["CAMUNDA_BASIC_AUTH_USERNAME"] == ""
    assert configuration["CAMUNDA_BASIC_AUTH_PASSWORD"] == ""

    invalid = basic.model_copy(update={"camunda_auth_mode": "oauth"})
    with pytest.raises(ValueError, match="only NONE or BASIC"):
        _client_configuration(invalid)


def test_create_app_uses_default_composition_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = make_settings()
    sessions = object()
    hasher = FastHasher()
    monkeypatch.setattr(main_module, "get_settings", lambda: configured)
    monkeypatch.setattr(main_module, "SessionFactory", sessions)
    monkeypatch.setattr(main_module, "PasswordHasher", lambda: hasher)

    application = create_app(start_background_worker=False)

    assert application.state.settings is configured
    assert application.state.session_factory is sessions
    assert application.state.password_hasher is hasher
    assert application.state.dummy_password_hash.startswith("test-hash:")


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
        start_background_worker=False,
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
        }
    ]
    assert sessions.sessions[0].entered == 0


@pytest.mark.asyncio
async def test_lifespan_creates_and_closes_camunda_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disable_organisation_seed(monkeypatch)
    configurations: list[dict[str, str]] = []
    events: list[object] = []
    engine = FakeWorkflowEngine()

    class ClientDouble:
        def __init__(self, *, configuration: Any) -> None:
            configurations.append(configuration)

        async def __aenter__(self) -> ClientDouble:
            events.append("entered")
            return self

        async def __aexit__(self, *args: object) -> None:
            events.append(("exited", args))

    monkeypatch.setattr(main_module, "CamundaAsyncClient", ClientDouble)
    monkeypatch.setattr(main_module, "CamundaWorkflowEngine", lambda _client: engine)
    application = create_app(
        settings=make_settings(),
        session_factory=cast(Any, SessionFactoryDouble()),
        password_hasher=FastHasher(),
        start_background_worker=False,
    )

    async with application.router.lifespan_context(application):
        assert application.state.workflow_engine is engine

    assert configurations[0]["CAMUNDA_REST_ADDRESS"].endswith("/v2")
    assert events[0] == "entered"
    assert events[1] == ("exited", (None, None, None))


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_maintenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disable_organisation_seed(monkeypatch)
    lifecycle: list[str] = []
    dispatcher = object()
    expected_command_dispatcher = object()
    reconciler = object()
    monkeypatch.setattr(
        main_module,
        "WorkflowOutboxDispatcher",
        lambda *_args, **_kwargs: dispatcher,
    )
    monkeypatch.setattr(
        main_module,
        "WorkflowReconciler",
        lambda *_args, **_kwargs: reconciler,
    )
    monkeypatch.setattr(
        main_module,
        "WorkflowCommandDispatcher",
        lambda *_args, **_kwargs: expected_command_dispatcher,
    )

    async def fake_maintenance(
        actual_dispatcher: object,
        actual_reconciler: object,
        stop: asyncio.Event,
        *,
        command_dispatcher: object,
        notification_reconciler: object | None,
    ) -> None:
        assert actual_dispatcher is dispatcher
        assert actual_reconciler is reconciler
        assert command_dispatcher is expected_command_dispatcher
        assert notification_reconciler is None
        lifecycle.append("started")
        await stop.wait()
        lifecycle.append("stopped")

    monkeypatch.setattr(main_module, "run_workflow_maintenance", fake_maintenance)
    application = create_app(
        settings=make_settings(),
        session_factory=cast(Any, SessionFactoryDouble()),
        workflow_engine=FakeWorkflowEngine(),
        password_hasher=FastHasher(),
        start_background_worker=True,
    )

    async with application.router.lifespan_context(application):
        await asyncio.sleep(0)
        assert lifecycle == ["started"]
    assert lifecycle == ["started", "stopped"]


@pytest.mark.asyncio
async def test_registered_service_error_handler_uses_stable_envelope() -> None:
    application = create_app(
        settings=make_settings(),
        workflow_engine=FakeWorkflowEngine(),
        password_hasher=FastHasher(),
        start_background_worker=False,
    )
    handler = application.exception_handlers[ServiceError]
    response = await handler(cast(Any, None), AuthenticationFailed())

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
) -> None:
    response = Response()
    session = HealthSessionDouble(database_ok)
    result = await readiness(
        response,
        cast(Any, session),
        cast(Any, HealthEngineDouble(workflow_ok)),
        make_settings(),
    )

    assert await health() == {"status": "ok"}
    assert response.status_code == expected_status
    assert result.status == ("ready" if expected_status == 200 else "not_ready")
    assert result.checks.database == ("ok" if database_ok else "unavailable")
    assert result.checks.workflow == ("ok" if workflow_ok else "unavailable")
    assert result.checks.configuration == "disabled"
    assert session.rollbacks == (0 if database_ok else 1)
