"""Exact-team planning cockpit, risk and scenario contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from conftest import ApiHarness
from istari_service.analytics_models import AnalyticsProjectionState, ProjectionHealth
from istari_service.analytics_projection import PROJECTION_NAME
from istari_service.board_models import IterationStatus, TeamIteration
from istari_service.planning_analytics_models import PlanningCapacityPreview
from planning_evolution_data import seed_planning


async def test_cockpit_templates_risks_and_capacity_preview(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    team_id, package_id = await seed_planning(harness)
    access = await harness.login("admin8")
    workspace = await harness.client.get("/api/v1/team-workspaces")
    team = next(
        item for item in workspace.json()["items"] if item["teamId"] == str(team_id)
    )
    cockpit = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/planning/cockpit"
    )
    assert cockpit.status_code == 200, cockpit.text
    body = cockpit.json()
    assert body["advisoryOnly"] is True
    assert body["freshness"]["health"] == "READY"
    assert body["summary"]["blockedCount"] == 3, cockpit.text
    assert body["iteration"]["committedPackages"] == 1
    assert body["checklists"][0]["completedCount"] == 1
    assert any(row["packageId"] == str(package_id) for row in body["blockers"])
    assert {row["status"] for row in body["dependencies"]} == {"BLOCKED", "MISSING"}
    assert "PRIVATE CALENDAR MARKER" not in cockpit.text
    templates = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/planning/templates"
    )
    assert templates.json()["items"][0]["checklist"][0]["required"] is True
    preview = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/planning/scenarios/preview",
        headers=harness.mutation_headers(),
        json={
            "grantId": team["grantId"],
            "name": "Synthetic surge option",
            "startsOn": datetime.now(UTC).date().isoformat(),
            "endsOn": (datetime.now(UTC).date() + timedelta(days=6)).isoformat(),
            "plannedMinutes": 600,
            "expectedSourceVersion": body["freshness"]["sourceVersion"],
        },
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["scenario"]["packageMinutes"] > 600
    assert {item["kind"] for item in preview.json()["conflicts"]} >= {
        "CAPACITY",
        "CALENDAR",
        "RESERVATION",
    }
    scenarios = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/planning/scenarios"
    )
    assert scenarios.json()["items"][0]["status"] == "PREVIEWED"
    async with harness.sessions() as session:
        stored = await session.scalar(select(PlanningCapacityPreview))
        assert stored is not None
        assert stored.team_id == team_id
        assert stored.created_by_user_id == UUID(access["user"]["id"])


async def test_planning_access_staleness_validation_and_empty_projection(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    team_id, _ = await seed_planning(harness)
    await harness.login("admin11")
    analyst = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/planning/cockpit"
    )
    assert analyst.status_code == 200
    denied_preview = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/planning/scenarios/preview",
        headers=harness.mutation_headers(),
        json={
            "grantId": str(uuid4()),
            "name": "Analyst option",
            "startsOn": datetime.now(UTC).date().isoformat(),
            "endsOn": datetime.now(UTC).date().isoformat(),
            "plannedMinutes": 60,
            "expectedSourceVersion": analyst.json()["freshness"]["sourceVersion"],
        },
    )
    assert denied_preview.status_code == 404
    await harness.login("admin8")
    workspace = await harness.client.get("/api/v1/team-workspaces")
    grant_id = next(
        item["grantId"]
        for item in workspace.json()["items"]
        if item["teamId"] == str(team_id)
    )
    stale = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/planning/scenarios/preview",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "name": "Stale option",
            "startsOn": datetime.now(UTC).date().isoformat(),
            "endsOn": datetime.now(UTC).date().isoformat(),
            "plannedMinutes": 60,
            "expectedSourceVersion": 1,
        },
    )
    assert stale.status_code == 409
    invalid = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/planning/scenarios/preview",
        headers=harness.mutation_headers(),
        json={
            "grantId": str(uuid4()),
            "name": "Invalid window",
            "startsOn": datetime.now(UTC).date().isoformat(),
            "endsOn": (datetime.now(UTC).date() + timedelta(days=91)).isoformat(),
            "plannedMinutes": 60,
            "expectedSourceVersion": 1,
        },
    )
    assert invalid.status_code == 422
    await harness.login("admin2")
    hidden = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/planning/templates"
    )
    assert hidden.status_code == 404
    await harness.login("admin24")
    quartz_id = await harness.unit_id("QUARTZ_TEAM")
    empty = await harness.client.get(
        f"/api/v1/team-workspaces/{quartz_id}/planning/cockpit"
    )
    assert empty.status_code == 200
    assert empty.json()["checklists"] == []
    assert empty.json()["iteration"] is None


async def test_planning_freshness_closed_iteration_and_reverse_window(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    team_id, _ = await seed_planning(harness)
    await harness.login("admin8")
    async with harness.sessions() as session, session.begin():
        state = await session.get(AnalyticsProjectionState, PROJECTION_NAME)
        iteration = await session.scalar(
            select(TeamIteration).where(TeamIteration.team_id == team_id)
        )
        assert state is not None and iteration is not None
        state.last_projected_at = datetime.now(UTC) - timedelta(hours=1)
        iteration.status = IterationStatus.CLOSED
    stale = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/planning/cockpit"
    )
    assert stale.status_code == 200
    assert stale.json()["freshness"]["health"] == "STALE"
    assert stale.json()["iteration"]["factualSummary"].endswith("points completed.")
    async with harness.sessions() as session, session.begin():
        state = await session.get(AnalyticsProjectionState, PROJECTION_NAME)
        assert state is not None
        state.health = ProjectionHealth.REBUILDING
    rebuilding = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/planning/cockpit"
    )
    assert rebuilding.json()["freshness"]["health"] == "REBUILDING"
    reverse = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/planning/scenarios/preview",
        headers=harness.mutation_headers(),
        json={
            "grantId": str(uuid4()),
            "name": "Reverse window",
            "startsOn": datetime.now(UTC).date().isoformat(),
            "endsOn": (datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
            "plannedMinutes": 60,
            "expectedSourceVersion": 1,
        },
    )
    assert reverse.status_code == 422
