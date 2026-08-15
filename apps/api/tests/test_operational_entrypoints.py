"""Focused branch coverage for privileged operational entry points."""

from __future__ import annotations

import argparse
from types import SimpleNamespace
from uuid import uuid4

import pytest

import mist_service.maintenance as maintenance
import mist_service.postgres_permissions as permissions
from operational_test_support import (
    FakeAsyncContext,
    FakeEngine,
    FakeReport,
    FakeSession,
    arguments,
)

_arguments = arguments


async def test_retention_entry_point_commits_apply_and_rolls_back_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        maintenance, "SessionFactory", lambda: FakeAsyncContext(session)
    )
    monkeypatch.setattr(
        maintenance,
        "get_settings",
        lambda: SimpleNamespace(
            maintenance_database_url="postgresql+asyncpg://synthetic",
            maintenance_operator_subject="synthetic-operator",
            maintenance_disposal_authority="RETENTION_DISPOSAL",
            audit_hmac_keys={"legacy": b"a" * 32},
            audit_hmac_active_key_id="legacy",
            model_copy=lambda **_values: SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(maintenance, "create_database_engine", lambda _s: FakeEngine())
    monkeypatch.setattr(
        maintenance,
        "create_session_factory",
        lambda *_args, **_kwargs: lambda: FakeAsyncContext(session),
    )

    class SuccessfulService:
        def __init__(self, _repository: object) -> None:
            pass

        async def run(self, **_values: object) -> FakeReport:
            return FakeReport()

    monkeypatch.setattr(maintenance, "RetentionService", SuccessfulService)
    monkeypatch.setattr(
        maintenance, "SqlAlchemyRetentionRepository", lambda value, *_args: value
    )
    report = await maintenance.run_retention(
        _arguments("retention", apply=True, confirm="APPLY_RETENTION", batch_size=5)
    )
    assert report == {"valid": True, "status": "ok", "value": "safe"}
    assert session.commits == 1
    await maintenance.run_retention(
        _arguments("retention", apply=False, confirm=None, batch_size=5)
    )
    assert session.commits == 1

    class FailingService(SuccessfulService):
        async def run(self, **_values: object) -> FakeReport:
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(maintenance, "RetentionService", FailingService)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        await maintenance.run_retention(
            _arguments("retention", apply=False, confirm=None, batch_size=5)
        )
    assert session.rollbacks == 1


async def test_maintenance_read_jobs_report_health_and_dispose(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session = FakeSession()
    disposed = 0

    async def dispose() -> None:
        nonlocal disposed
        disposed += 1

    async def verify(_session: object, *, expected_revision: str) -> FakeReport:
        assert expected_revision == "head"
        return FakeReport(valid=False)

    async def snapshot(_session: object, **limits: int) -> FakeReport:
        assert limits == {
            "max_command_age_seconds": 10,
            "max_projection_age_seconds": 20,
        }
        return FakeReport(status="warning")

    monkeypatch.setattr(
        maintenance, "SessionFactory", lambda: FakeAsyncContext(session)
    )
    monkeypatch.setattr(maintenance, "dispose_database", dispose)
    monkeypatch.setattr(maintenance, "verify_restored_database", verify)
    monkeypatch.setattr(maintenance, "capture_operational_snapshot", snapshot)

    restore_code = await maintenance.async_main(
        _arguments("verify-restore", expected_revision="head")
    )
    snapshot_code = await maintenance.async_main(
        _arguments(
            "health-snapshot",
            max_command_age_seconds=10,
            max_projection_age_seconds=20,
        )
    )
    assert restore_code == snapshot_code == 2
    assert disposed == 2
    assert '"valid": false' in capsys.readouterr().out


async def test_maintenance_dispatches_retention_job(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def retention(arguments: argparse.Namespace) -> dict[str, object]:
        assert arguments.batch_size == 25
        return {"applied": False}

    async def dispose() -> None:
        return None

    monkeypatch.setattr(maintenance, "run_retention", retention)
    monkeypatch.setattr(maintenance, "dispose_database", dispose)
    result = await maintenance.async_main(
        _arguments("retention", apply=False, confirm=None, batch_size=25)
    )
    assert result == 0
    assert capsys.readouterr().out.strip() == '{"applied": false}'


async def test_maintenance_mutating_jobs_and_invalid_job(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session = FakeSession()
    request_id = uuid4()
    attestations: list[maintenance.WorkflowAttestation] = []

    async def recover(
        _session: object, received_id: object, **options: object
    ) -> FakeReport:
        assert received_id == request_id
        assert options == {"apply": True, "confirmation": "confirmed"}
        return FakeReport()

    async def attest(
        _session: object,
        command: maintenance.WorkflowAttestation,
        **options: object,
    ) -> bool:
        attestations.append(command)
        assert options == {"apply": False, "confirmation": None}
        return True

    async def dispose() -> None:
        return None

    monkeypatch.setattr(
        maintenance, "SessionFactory", lambda: FakeAsyncContext(session)
    )
    monkeypatch.setattr(maintenance, "recover_failed_workflow", recover)
    monkeypatch.setattr(maintenance, "attest_workflow_availability", attest)
    monkeypatch.setattr(maintenance, "dispose_database", dispose)

    assert (
        await maintenance.async_main(
            _arguments(
                "workflow-recovery",
                request_id=request_id,
                apply=True,
                confirm="confirmed",
            )
        )
        == 0
    )
    assert (
        await maintenance.async_main(
            _arguments(
                "attest-workflow",
                process_id="service-request",
                process_version=1,
                process_definition_key="definition",
                deployment_key="deployment",
                compatibility_key="compatible",
                checksum="a" * 64,
                operator_subject="operator",
                apply=False,
                confirm=None,
            )
        )
        == 0
    )
    assert attestations[0].checksum == "a" * 64
    assert '"applied": false' in capsys.readouterr().out
    with pytest.raises(ValueError, match="unsupported maintenance job"):
        await maintenance.async_main(_arguments("unknown"))


def test_maintenance_main_parses_and_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    arguments = _arguments("synthetic")

    class FakeParser:
        def parse_args(self) -> argparse.Namespace:
            return arguments

    async def fake_main(received: argparse.Namespace) -> int:
        assert received is arguments
        return 7

    monkeypatch.setattr(maintenance, "parser", FakeParser)
    monkeypatch.setattr(maintenance, "async_main", fake_main)
    assert maintenance.main() == 7


@pytest.mark.parametrize("database_url", [None, "sqlite+aiosqlite:///unsafe.db"])
async def test_permission_application_requires_async_postgresql_url(
    monkeypatch: pytest.MonkeyPatch, database_url: str | None
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    if database_url is not None:
        monkeypatch.setenv("DATABASE_URL", database_url)
    with pytest.raises(ValueError, match="async PostgreSQL migration URL"):
        await permissions.apply_permissions()


async def test_permission_application_executes_reviewed_grants_and_disposes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = FakeEngine()
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://owner:test@db/app")
    monkeypatch.setenv("APP_RUNTIME_DATABASE_USER", "mist_runtime")
    monkeypatch.setenv("APP_BACKUP_DATABASE_USER", "mist_backup")
    monkeypatch.setattr(permissions, "create_async_engine", lambda *_a, **_k: engine)

    await permissions.apply_permissions()

    assert engine.statements == list(
        permissions.permission_statements("mist_runtime", "mist_backup")
    )
    assert engine.disposed


async def test_permission_application_rejects_wrong_dialect_and_disposes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = FakeEngine("sqlite")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://owner:test@db/app")
    monkeypatch.setenv("APP_RUNTIME_DATABASE_USER", "mist_runtime")
    monkeypatch.setenv("APP_BACKUP_DATABASE_USER", "mist_backup")
    monkeypatch.setattr(permissions, "create_async_engine", lambda *_a, **_k: engine)
    with pytest.raises(ValueError, match="require PostgreSQL"):
        await permissions.apply_permissions()
    assert engine.disposed


def test_permission_role_length_and_main(monkeypatch: pytest.MonkeyPatch) -> None:
    assert permissions.permission_statements("r" * 63, "b" * 63)
    with pytest.raises(ValueError, match="PostgreSQL role name"):
        permissions.permission_statements("r" * 64, "backup")

    called = False

    async def apply() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(permissions, "apply_permissions", apply)
    permissions.main()
    assert called
