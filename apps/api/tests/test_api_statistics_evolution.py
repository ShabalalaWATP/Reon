"""Scoped, suppressed operational evolution statistics and export policy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from conftest import ApiHarness
from mist_service.analytics_evolution_models import (
    AnalyticsAggregateExport,
    AnalyticsExportAuditEvent,
    AnalyticsExportStatus,
)
from mist_service.management_seed import management_grant_id
from statistics_evolution_data import seed_evolution_statistics


def _params(scope_id: str) -> dict[str, str]:
    today = datetime.now(ZoneInfo("Europe/London")).date()
    return {
        "scopeId": scope_id,
        "from": (today - timedelta(days=9)).isoformat(),
        "to": today.isoformat(),
        "timeZone": "Europe/London",
    }


async def test_evolution_metrics_and_fail_closed_export_audit(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await seed_evolution_statistics(harness)
    await harness.login("admin6")
    params = _params(str(management_grant_id("admin6", "ACSA_B_OPS")))
    response = await harness.client.get("/api/v1/statistics/evolution", params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    comparisons = {item["key"]: item for item in body["comparison"]}
    assert comparisons["received"]["current"] == 5
    assert comparisons["received"]["previous"] == 5
    assert body["bottlenecks"][0]["suppressed"] is False
    assert body["bottlenecks"][0]["activeCount"] == 2
    assert len(body["capacity"]) == 1
    releases = {item["key"]: item for item in body["releases"]}
    assert releases["dissemination_released"]["medianHours"] == 3.0
    assert releases["dissemination_withdrawn"]["count"] is None
    assert body["notifications"][0]["unresolvedCount"] == 1
    assert body["iterations"][0]["completionPercentage"] == 80.0
    assert len(body["projection"]["periods"]) == 14
    assert body["exports"]["csv"]["state"] == "DENIED"
    assert "PROHIBITED CONTENT MARKER" not in response.text
    assert "sourceKey" not in response.text
    exported = await harness.client.post(
        "/api/v1/statistics/exports",
        headers=harness.mutation_headers(),
        json={**params, "format": "CSV"},
    )
    assert exported.status_code == 200, exported.text
    assert exported.json()["state"] == "PENDING"
    assert exported.json()["downloadUrl"] is None
    async with harness.sessions() as session:
        record = await session.scalar(select(AnalyticsAggregateExport))
        event = await session.scalar(select(AnalyticsExportAuditEvent))
        assert record is not None and event is not None
        assert record.status is AnalyticsExportStatus.DENIED
        assert record.version == 1
        assert event.to_status is AnalyticsExportStatus.DENIED
        event.reason = "Mutation must fail."
        with pytest.raises(ValueError, match="append-only"):
            await session.flush()


async def test_small_cohorts_platform_health_scope_and_invalid_queries(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await seed_evolution_statistics(harness)
    await harness.login("admin6")
    small_params = _params(str(management_grant_id("admin6", "NIMBUS_OPS")))
    small = await harness.client.get(
        "/api/v1/statistics/evolution", params=small_params
    )
    assert small.status_code == 200
    assert all(item["current"] is None for item in small.json()["comparison"])
    assert small.json()["bottlenecks"][0]["activeCount"] is None
    assert small.json()["releases"][0]["count"] is None
    assert small.json()["notifications"][0]["count"] is None
    assert small.json()["capacity"] == []
    assert small.json()["projection"]["periods"] == []
    missing_csrf = await harness.client.post(
        "/api/v1/statistics/exports", json={**small_params, "format": "PDF"}
    )
    assert missing_csrf.status_code == 403
    await harness.login("admin1")
    platform = await harness.client.get(
        "/api/v1/statistics/evolution", params=_params("platform")
    )
    assert platform.status_code == 200
    assert platform.json()["comparison"] == []
    assert platform.json()["releases"] == []
    assert platform.json()["exports"]["pdf"]["state"] == "DENIED"
    platform_export = await harness.client.post(
        "/api/v1/statistics/exports",
        headers=harness.mutation_headers(),
        json={**_params("platform"), "format": "CSV"},
    )
    assert platform_export.status_code == 200
    assert platform_export.json()["state"] == "PENDING"
    await harness.login("admin10")
    sibling = await harness.client.get(
        "/api/v1/statistics/evolution",
        params=_params(str(management_grant_id("admin6", "ACSA_B_OPS"))),
    )
    assert sibling.status_code == 404
    await harness.login("admin2")
    hidden = await harness.client.get(
        "/api/v1/statistics/evolution", params=small_params
    )
    assert hidden.status_code == 404
    await harness.login("admin6")
    today = datetime.now(UTC).date()
    invalid_queries = (
        {**small_params, "timeZone": "Not/AZone"},
        {
            **small_params,
            "from": today.isoformat(),
            "to": (today - timedelta(days=1)).isoformat(),
        },
        {
            **small_params,
            "from": (today - timedelta(days=366)).isoformat(),
            "to": today.isoformat(),
        },
    )
    for invalid in invalid_queries:
        response = await harness.client.get(
            "/api/v1/statistics/evolution", params=invalid
        )
        assert response.status_code == 422
    invalid_exports = (
        {
            **small_params,
            "from": today.isoformat(),
            "to": (today - timedelta(days=1)).isoformat(),
            "format": "CSV",
        },
        {
            **small_params,
            "from": (today - timedelta(days=366)).isoformat(),
            "to": today.isoformat(),
            "format": "PDF",
        },
    )
    for invalid in invalid_exports:
        response = await harness.client.post(
            "/api/v1/statistics/exports",
            headers=harness.mutation_headers(),
            json=invalid,
        )
        assert response.status_code == 422
