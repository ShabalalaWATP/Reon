"""Scope-aware operational statistics through the public API contract."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from conftest import ApiHarness, request_payload
from istari_service.analytics_models import (
    AnalyticsProjectionState,
    ProjectionHealth,
    RequestAnalyticsFact,
    RequestStageInterval,
)
from istari_service.analytics_projection import PROJECTION_NAME, PROJECTION_VERSION
from istari_service.management_seed import management_grant_id
from istari_service.models import RequestStatus, ServiceRequest
from istari_service.schemas.requests import RequestCreate


async def _seed_statistics(harness: ApiHarness) -> None:
    now = datetime.now(UTC)
    requester_id = await harness.user_id("admin2")
    unit_codes = (
        "JIOC",
        "DIGOC",
        "NCGI_A_OPS",
        "OSG_TEAM",
        "AURORA_OPS",
        "LANTERN_TEAM",
        "SYGOC",
        "NIMBUS_OPS",
        "BEACON_TEAM",
        "MYGOC",
        "MERIDIAN_OPS",
        "FLINT_TEAM",
    )
    unit_ids = {code: await harness.unit_id(code) for code in unit_codes}
    rows = [
        (
            "DIGOC",
            "NCGI_A_OPS",
            "OSG_TEAM",
            RequestStatus.COMPLETED,
            rating,
            8 - rating,
            10,
        )
        for rating in range(1, 6)
    ]
    rows.extend(
        (
            ("DIGOC", "NCGI_A_OPS", "OSG_TEAM", RequestStatus.IN_PROGRESS, None, 1, -1),
            (
                "DIGOC",
                "AURORA_OPS",
                "LANTERN_TEAM",
                RequestStatus.IN_PROGRESS,
                None,
                2,
                3,
            ),
            ("SYGOC", "NIMBUS_OPS", "BEACON_TEAM", RequestStatus.COMPLETED, 5, 3, 8),
            (
                "SYGOC",
                "NIMBUS_OPS",
                "BEACON_TEAM",
                RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
                None,
                0,
                6,
            ),
            (
                "MYGOC",
                "MERIDIAN_OPS",
                "FLINT_TEAM",
                RequestStatus.CLOSED_NOT_PROGRESSED,
                None,
                4,
                12,
            ),
        )
    )
    async with harness.sessions() as session, session.begin():
        for index, (command, ops, team, status, rating, age, due_offset) in enumerate(
            rows
        ):
            request_id = uuid4()
            received_at = now - timedelta(days=age)
            command_data = RequestCreate.model_validate(request_payload()).model_dump()
            request = ServiceRequest(
                id=request_id,
                reference=f"SR-STATS-{index:03d}",
                requester_id=requester_id,
                status=status,
                current_owner="Synthetic statistics fixture",
                created_at=received_at,
                **command_data,
            )
            request.title = f"Content marker {index} must not enter statistics"
            request.required_by = now.date() + timedelta(days=due_offset)
            completed_at = (
                received_at + timedelta(hours=8)
                if status is RequestStatus.COMPLETED
                else None
            )
            session.add(request)
            session.add(
                RequestAnalyticsFact(
                    request_id=request_id,
                    root_unit_id=unit_ids["JIOC"],
                    command_unit_id=unit_ids[command],
                    ops_unit_id=unit_ids[ops],
                    team_unit_id=unit_ids[team],
                    received_at=received_at,
                    required_by=request.required_by,
                    current_status=status,
                    last_transition_at=completed_at or received_at,
                    completed_at=completed_at,
                    closed_at=(
                        received_at + timedelta(hours=2)
                        if status is RequestStatus.CLOSED_NOT_PROGRESSED
                        else None
                    ),
                    released_at=completed_at,
                    clarification_count=2 if index == 5 else 0,
                    clarification_response_seconds=7200 if index == 5 else 0,
                    rework_count=1 if index == 5 else 0,
                    feedback_received=rating is not None,
                    feedback_rating=rating,
                    projection_version=PROJECTION_VERSION,
                    source_event_count=1,
                    projected_at=now,
                )
            )
            session.add(
                RequestStageInterval(
                    request_id=request_id,
                    sequence=1,
                    status=RequestStatus.IN_PROGRESS,
                    unit_id=unit_ids[team],
                    started_at=received_at,
                    ended_at=received_at + timedelta(hours=index + 1),
                    duration_seconds=(index + 1) * 3600,
                    source_event_id=None,
                )
            )
        session.add(
            AnalyticsProjectionState(
                name=PROJECTION_NAME,
                projection_version=PROJECTION_VERSION,
                health=ProjectionHealth.READY,
                source_event_count=len(rows),
                projected_request_count=len(rows),
                last_projected_at=now,
            )
        )


async def test_scope_catalogues_are_explicit_and_cross_branch_access_is_denied(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    expected = {
        "admin1": ["Whole platform"],
        "admin4": ["JIOC"],
        "admin5": ["DIGOC", "SYGOC", "MYGOC"],
        "admin6": [
            "NCGI-A Ops",
            "Aurora Ops",
            "Vertex Ops",
            "Nimbus Ops",
            "Parallax Ops",
        ],
        "admin10": ["Horizon Ops", "Meridian Ops", "Solstice Ops", "Frontier Ops"],
        "admin8": ["OSG Team"],
        "admin2": [],
    }
    for username, names in expected.items():
        await harness.login(username)
        response = await harness.client.get("/api/v1/statistics/scopes")
        assert response.status_code == 200
        assert [item["name"] for item in response.json()["items"]] == names

    await harness.login("admin6")
    attack = await harness.client.get(
        "/api/v1/statistics",
        params={
            "scopeId": str(management_grant_id("admin5", "SYGOC")),
            "from": (datetime.now(UTC).date() - timedelta(days=30)).isoformat(),
            "to": datetime.now(UTC).date().isoformat(),
        },
    )
    assert attack.status_code == 404
    platform_attack = await harness.client.get(
        "/api/v1/statistics",
        params={"scopeId": "platform"},
    )
    assert platform_attack.status_code == 404


async def test_dashboards_show_only_the_authorised_operational_branch(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _seed_statistics(harness)
    today = datetime.now(ZoneInfo("Europe/London")).date()
    date_params = {
        "from": (today - timedelta(days=30)).isoformat(),
        "to": today.isoformat(),
        "timeZone": "Europe/London",
    }
    await harness.login("admin6")
    ncgi = await harness.client.get(
        "/api/v1/statistics",
        params={
            **date_params,
            "scopeId": str(management_grant_id("admin6", "NCGI_A_OPS")),
        },
    )
    assert ncgi.status_code == 200, ncgi.text
    body = ncgi.json()
    metrics = {item["key"]: item for item in body["summary"]}
    assert body["scope"]["name"] == "NCGI-A Ops"
    assert metrics["received"]["value"] == 6
    assert metrics["active"]["value"] == 1
    assert metrics["completed"]["value"] == 5
    assert metrics["overdue"]["value"] == 1
    assert metrics["average_rating"] == {
        "key": "average_rating",
        "label": "Average rating",
        "value": 3.0,
        "unit": "rating",
        "suppressed": False,
    }
    assert [child["name"] for child in body["children"]] == [
        "OSG Team",
        "Cedar Team",
        "Quartz Team",
    ]
    assert body["children"][0]["received"] == 6
    assert body["children"][0]["averageRating"] == 3.0
    assert "Content marker" not in ncgi.text
    assert "requestId" not in ncgi.text

    await harness.login("admin5")
    digoc = await harness.client.get(
        "/api/v1/statistics",
        params={
            **date_params,
            "scopeId": str(management_grant_id("admin5", "DIGOC")),
        },
    )
    assert digoc.status_code == 200
    assert {child["name"]: child["received"] for child in digoc.json()["children"]} == {
        "NCGI-A Ops": 6,
        "Aurora Ops": 1,
        "Vertex Ops": 0,
    }
    assert "Nimbus Ops" not in digoc.text

    await harness.login("admin8")
    team = await harness.client.get(
        "/api/v1/statistics",
        params={
            **date_params,
            "scopeId": str(management_grant_id("admin8", "OSG_TEAM")),
        },
    )
    assert team.status_code == 200
    assert team.json()["children"] == []
    assert team.json()["summary"][0]["value"] == 6

    await harness.login("admin1")
    platform = await harness.client.get(
        "/api/v1/statistics",
        params={**date_params, "scopeId": "platform"},
    )
    assert platform.status_code == 200
    assert platform.json()["summary"][0]["value"] == 10
    assert [child["name"] for child in platform.json()["children"]] == [
        "DIGOC",
        "SYGOC",
        "MYGOC",
    ]


async def test_statistics_filters_and_small_ratings_fail_safely(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _seed_statistics(harness)
    await harness.login("admin6")
    scope_id = str(management_grant_id("admin6", "NIMBUS_OPS"))
    today = datetime.now(UTC).date()
    response = await harness.client.get(
        "/api/v1/statistics",
        params={
            "scopeId": scope_id,
            "from": (today - timedelta(days=30)).isoformat(),
            "to": today.isoformat(),
        },
    )
    rating = {row["key"]: row for row in response.json()["summary"]}["average_rating"]
    assert rating["value"] is None
    assert rating["suppressed"] is True
    invalid_queries = (
        {
            "scopeId": scope_id,
            "from": today.isoformat(),
            "to": (today - timedelta(days=1)).isoformat(),
        },
        {
            "scopeId": scope_id,
            "from": (today - timedelta(days=366)).isoformat(),
            "to": today.isoformat(),
        },
        {"scopeId": scope_id, "timeZone": "Not/AZone"},
    )
    for params in invalid_queries:
        invalid = await harness.client.get("/api/v1/statistics", params=params)
        assert invalid.status_code == 422
