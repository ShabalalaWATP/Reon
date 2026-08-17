"""Scope-aware operational statistics through the public API contract."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from conftest import ApiHarness
from mist_service.management_seed import management_grant_id
from mist_service.qc_membership import QC_TEAM_ID
from mist_service.team_models import TeamMembership, WorkspacePosition
from statistics_test_support import seed_statistics


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


async def test_qc_statistics_grant_requires_live_manager_position(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin15")
    before = await harness.client.get("/api/v1/statistics/scopes")
    assert before.status_code == 200
    assert [item["name"] for item in before.json()["items"]] == ["JIOC"]

    async with harness.sessions() as session, session.begin():
        membership = await session.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == await harness.user_id("admin15"),
                TeamMembership.team_id == QC_TEAM_ID,
                TeamMembership.effective_until.is_(None),
            )
        )
        assert membership is not None
        membership.workspace_position = WorkspacePosition.MEMBER

    after = await harness.client.get("/api/v1/statistics/scopes")
    assert after.status_code == 200
    assert after.json() == {"items": []}
    direct = await harness.client.get(
        "/api/v1/statistics",
        params={"scopeId": str(management_grant_id("admin15", "CRIOC"))},
    )
    assert direct.status_code == 404


async def test_dashboards_show_only_the_authorised_operational_branch(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await seed_statistics(harness)
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
            "scopeId": str(management_grant_id("admin6", "ACSA_B_OPS")),
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
    jock = await harness.client.get(
        "/api/v1/statistics",
        params={
            **date_params,
            "scopeId": str(management_grant_id("admin5", "JOCK")),
        },
    )
    assert jock.status_code == 200
    assert {child["name"]: child["received"] for child in jock.json()["children"]} == {
        "NCGI-A Ops": 6,
        "Aurora Ops": 1,
        "Vertex Ops": 0,
    }
    assert "Nimbus Ops" not in jock.text

    await harness.login("admin8")
    team = await harness.client.get(
        "/api/v1/statistics",
        params={
            **date_params,
            "scopeId": str(management_grant_id("admin8", "SSG_TEAM")),
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
    await seed_statistics(harness)
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


async def test_statistics_grant_can_select_descendants_but_not_siblings(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await seed_statistics(harness)
    today = datetime.now(UTC).date()
    dates = {
        "from": (today - timedelta(days=30)).isoformat(),
        "to": today.isoformat(),
    }
    crioc_scope = str(management_grant_id("admin4", "CRIOC"))
    ncgi_id = await harness.unit_id("ACSA_B_OPS")
    ssg_id = await harness.unit_id("SSG_TEAM")
    await harness.login("admin4")
    descendant = await harness.client.get(
        "/api/v1/statistics",
        params={**dates, "scopeId": crioc_scope, "unitId": str(ssg_id)},
    )
    assert descendant.status_code == 200, descendant.text
    assert descendant.json()["selectedUnit"]["name"] == "OSG Team"
    assert [item["name"] for item in descendant.json()["breadcrumb"]] == [
        "JIOC",
        "DIGOC",
        "NCGI-A Ops",
        "OSG Team",
    ]
    assert descendant.json()["summary"][0]["value"] == 6

    ncgi_scope = str(management_grant_id("admin6", "ACSA_B_OPS"))
    aurora_id = await harness.unit_id("AURORA_OPS")
    await harness.login("admin6")
    own_team = await harness.client.get(
        "/api/v1/statistics",
        params={**dates, "scopeId": ncgi_scope, "unitId": str(ssg_id)},
    )
    assert own_team.status_code == 200
    sibling = await harness.client.get(
        "/api/v1/statistics",
        params={**dates, "scopeId": ncgi_scope, "unitId": str(aurora_id)},
    )
    assert sibling.status_code == 404

    await harness.login("admin5")
    parent = await harness.client.get(
        "/api/v1/statistics",
        params={
            **dates,
            "scopeId": str(management_grant_id("admin5", "JOCK")),
            "unitId": str(await harness.unit_id("CRIOC")),
        },
    )
    other_grant_root = await harness.client.get(
        "/api/v1/statistics",
        params={
            **dates,
            "scopeId": str(management_grant_id("admin5", "JOCK")),
            "unitId": str(await harness.unit_id("SYGOC")),
        },
    )
    assert parent.status_code == 404
    assert other_grant_root.status_code == 404
    assert ncgi_id != aurora_id
