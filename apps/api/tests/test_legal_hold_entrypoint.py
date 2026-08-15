"""Fail-closed privileged legal-hold maintenance entry-point tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import mist_service.maintenance as maintenance
from operational_test_support import (
    FakeAsyncContext,
    FakeEngine,
    FakeSession,
    arguments,
)


@pytest.mark.parametrize(
    ("subject", "authority", "database_url", "message"),
    [
        (None, "LEGAL_HOLD", "postgresql+asyncpg://synthetic", "identity"),
        ("operator", None, "postgresql+asyncpg://synthetic", "identity"),
        ("operator", "LEGAL_HOLD", None, "MAINTENANCE_DATABASE_URL"),
    ],
)
async def test_legal_hold_requires_separate_authority_and_database(
    monkeypatch: pytest.MonkeyPatch,
    subject: str | None,
    authority: str | None,
    database_url: str | None,
    message: str,
) -> None:
    monkeypatch.setattr(
        maintenance,
        "get_settings",
        lambda: SimpleNamespace(
            maintenance_operator_subject=subject,
            maintenance_legal_hold_authority=authority,
            maintenance_database_url=database_url,
        ),
    )
    with pytest.raises(ValueError, match=message):
        await maintenance.run_legal_hold(_command("apply"))


@pytest.mark.parametrize("action", ["apply", "release"])
async def test_legal_hold_applies_or_releases_and_disposes(
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    session, engine = _configure_maintenance(monkeypatch)
    target_id = uuid4()
    expected_id = uuid4()

    class FakeService:
        def __init__(self, value: object, *, subject: str, authority: str) -> None:
            assert value is session
            assert (subject, authority) == ("synthetic-operator", "LEGAL_HOLD")

        async def apply(
            self, target_type: str, received_id: object, reason: str
        ) -> object:
            assert (target_type, received_id, reason) == (
                "SECURITY_EVENT",
                target_id,
                "SYNTHETIC_TEST",
            )
            return SimpleNamespace(id=expected_id)

        async def release(self, target_type: str, received_id: object) -> object:
            assert (target_type, received_id) == ("SECURITY_EVENT", target_id)
            return SimpleNamespace(id=expected_id)

    monkeypatch.setattr(maintenance, "LegalHoldService", FakeService)
    result = await maintenance.run_legal_hold(_command(action, target_id))
    assert result == {"id": str(expected_id), "action": action}
    assert engine.disposed


async def test_legal_hold_disposes_after_service_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _session, engine = _configure_maintenance(monkeypatch)

    class FailingService:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def apply(self, *_args: object) -> object:
            raise RuntimeError("synthetic legal-hold failure")

    monkeypatch.setattr(maintenance, "LegalHoldService", FailingService)
    with pytest.raises(RuntimeError, match="synthetic legal-hold failure"):
        await maintenance.run_legal_hold(_command("apply"))
    assert engine.disposed


def _command(action: str, target_id: object | None = None):
    return arguments(
        "legal-hold",
        action=action,
        target_type="SECURITY_EVENT",
        target_id=target_id or uuid4(),
        reason_code="SYNTHETIC_TEST",
    )


def _configure_maintenance(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[FakeSession, FakeEngine]:
    session = FakeSession()
    engine = FakeEngine()
    monkeypatch.setattr(
        maintenance,
        "get_settings",
        lambda: SimpleNamespace(
            maintenance_operator_subject="synthetic-operator",
            maintenance_legal_hold_authority="LEGAL_HOLD",
            maintenance_database_url="postgresql+asyncpg://synthetic",
            audit_hmac_keys={"legacy": b"a" * 32},
            audit_hmac_active_key_id="legacy",
            model_copy=lambda **_values: SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(maintenance, "create_database_engine", lambda _s: engine)
    monkeypatch.setattr(
        maintenance,
        "create_session_factory",
        lambda *_args, **_kwargs: lambda: FakeAsyncContext(session),
    )
    return session, engine
