"""Complete Board aggregates remain truthful across cursor pages."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import ApiHarness


async def test_board_column_totals_are_independent_of_cursor_pages(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin8")
    team_id = str(await harness.unit_id("OSG_TEAM"))
    workspaces = await harness.client.get("/api/v1/team-workspaces")
    osg = next(item for item in workspaces.json()["items"] if item["teamId"] == team_id)
    owner_id = str(await harness.user_id("admin11"))
    contributor_id = str(await harness.user_id("admin12"))
    due_on = (datetime.now(UTC).date() + timedelta(days=14)).isoformat()
    for sequence in range(2):
        response = await harness.client.post(
            f"/api/v1/team-workspaces/{team_id}/packages",
            headers=harness.mutation_headers(),
            json={
                "grantId": osg["grantId"],
                "title": f"Bounded package {sequence + 1}",
                "description": "Complete synthetic package context for pagination.",
                "ownerUserId": owner_id,
                "contributorIds": [contributor_id],
                "estimatePoints": 3,
                "remainingEffortMinutes": 120,
                "dueOn": due_on,
                "priority": "HIGH",
                "blockers": "No known blockers at the time of planning.",
                "acceptanceCriteria": "The complete synthetic package is delivered.",
                "linkedRequestId": None,
                "dependencyIds": [],
                "iterationId": None,
            },
        )
        assert response.status_code == 200, response.text

    first_page = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/board",
        params={"itemType": "WORK_PACKAGE", "column": "BACKLOG", "limit": 1},
    )
    assert first_page.status_code == 200, first_page.text
    result = first_page.json()
    assert len(result["items"]) == 1
    assert result["nextCursor"] is not None
    assert result["columnCounts"]["BACKLOG"] == 2
    assert result["totalCount"] == 2

    searched = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/board",
        params={"itemType": "WORK_PACKAGE", "search": "package 1", "limit": 1},
    )
    assert searched.status_code == 200
    assert searched.json()["columnCounts"]["BACKLOG"] == 1
    assert searched.json()["totalCount"] == 1
