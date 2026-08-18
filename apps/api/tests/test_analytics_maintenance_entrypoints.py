"""Bounded operator entry points for analytics recovery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

import mist_service.maintenance as maintenance
from operational_test_support import (
    FakeAsyncContext,
    FakeReport,
    FakeSession,
    arguments,
)


async def test_maintenance_dispatches_bounded_analytics_recovery(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session = FakeSession()
    now = datetime.now(UTC)
    calls: list[tuple[str, object]] = []

    async def rebuild(_session: object, *, request_limit: int) -> int:
        calls.append(("rebuild", request_limit))
        return 12

    async def replay(
        _session: object,
        *,
        start: datetime,
        end: datetime,
        source_limit: int,
    ) -> FakeReport:
        calls.append(("replay", (start, end, source_limit)))
        return FakeReport()

    async def dispose() -> None:
        return None

    monkeypatch.setattr(
        maintenance, "SessionFactory", lambda: FakeAsyncContext(session)
    )
    monkeypatch.setattr(maintenance, "rebuild_analytics_projections", rebuild)
    monkeypatch.setattr(maintenance, "reconcile_operational_analytics", replay)
    monkeypatch.setattr(maintenance, "dispose_database", dispose)

    assert (
        await maintenance.async_main(arguments("rebuild-analytics", request_limit=25))
        == 0
    )
    assert (
        await maintenance.async_main(
            arguments(
                "replay-operational-analytics",
                start=now,
                end=now + timedelta(hours=1),
                source_limit=50,
            )
        )
        == 0
    )
    assert calls == [
        ("rebuild", 25),
        ("replay", (now, now + timedelta(hours=1), 50)),
    ]
    output = capsys.readouterr().out
    assert '"rebuilt_requests": 12' in output
    assert '"status": "ok"' in output


def test_maintenance_parser_accepts_utc_analytics_recovery_bounds() -> None:
    parsed = maintenance.parser().parse_args(
        [
            "replay-operational-analytics",
            "--start",
            "2026-08-17T00:00:00+00:00",
            "--end",
            "2026-08-18T00:00:00+00:00",
            "--source-limit",
            "25",
        ]
    )
    assert parsed.start == datetime(2026, 8, 17, tzinfo=UTC)
    assert parsed.end == datetime(2026, 8, 18, tzinfo=UTC)
    assert parsed.source_limit == 25
