"""Exact-team board and agile-planning journeys through the public API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from conftest import ApiHarness
from istari_service.board_models import WorkPackage, WorkPackageStatus


async def workspace(harness: ApiHarness, username: str = "admin8") -> dict[str, Any]:
    await harness.login(username)
    response = await harness.client.get("/api/v1/team-workspaces")
    assert response.status_code == 200
    team_id = str(await harness.unit_id("OSG_TEAM"))
    return next(item for item in response.json()["items"] if item["teamId"] == team_id)


def package_command(
    grant_id: str | None,
    owner_id: str,
    contributor_id: str,
    **updates: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "grantId": grant_id,
        "title": "Prepare the customer service product",
        "description": "Produce and check the complete synthetic service product.",
        "ownerUserId": owner_id,
        "contributorIds": [contributor_id],
        "estimatePoints": 5,
        "remainingEffortMinutes": 240,
        "dueOn": (datetime.now(UTC).date() + timedelta(days=14)).isoformat(),
        "priority": "HIGH",
        "blockers": "No known blockers at the time of planning.",
        "acceptanceCriteria": "The agreed customer outcomes are fully addressed.",
        "linkedRequestId": None,
        "dependencyIds": [],
        "iterationId": None,
    }
    body.update(updates)
    return body


async def test_manager_board_package_iteration_and_capacity_lifecycle(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    osg = await workspace(harness)
    team_id, grant_id = osg["teamId"], osg["grantId"]
    owner_id = str(await harness.user_id("admin11"))
    contributor_id = str(await harness.user_id("admin12"))
    today = datetime.now(UTC).date()

    iteration = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/iterations",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "name": "Pilot iteration one",
            "goal": "Deliver the first fully traceable synthetic work package.",
            "startsOn": today.isoformat(),
            "endsOn": (today + timedelta(days=14)).isoformat(),
        },
    )
    assert iteration.status_code == 200, iteration.text
    assert iteration.json()["status"] == "ACTIVE"
    iteration_id = iteration.json()["id"]

    created = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/packages",
        headers=harness.mutation_headers(),
        json=package_command(
            grant_id, owner_id, contributor_id, iterationId=iteration_id
        ),
    )
    assert created.status_code == 200, created.text
    package = created.json()
    assert package["status"] == "BACKLOG"
    assert package["ownerUserId"] == owner_id
    assert package["contributors"][0]["userId"] == contributor_id
    assert package["activities"][0]["type"] == "CREATED"

    people = await harness.client.get(f"/api/v1/team-workspaces/{team_id}/people")
    owner_membership = next(
        item for item in people.json()["items"] if item["accountId"] == owner_id
    )
    assert owner_membership["activeWorkCount"] == 1
    package_block = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/memberships/"
        f"{owner_membership['membershipId']}/end",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "expectedVersion": owner_membership["version"],
            "reason": "The package must be reassigned before this roster change.",
        },
    )
    assert package_block.status_code == 409
    assert "work packages" in package_block.json()["detail"]["message"]

    package_id = package["id"]
    detail = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/packages/{package_id}"
    )
    listed = await harness.client.get(f"/api/v1/team-workspaces/{team_id}/packages")
    assert detail.status_code == listed.status_code == 200
    assert listed.json()["items"][0]["id"] == package_id

    board = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/board",
        params={"search": "customer", "itemType": "WORK_PACKAGE", "limit": 1},
    )
    assert board.status_code == 200, board.text
    assert board.json()["items"][0]["column"] == "BACKLOG"
    invalid_cursor = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/board", params={"cursor": "invalid"}
    )
    assert invalid_cursor.status_code == 409

    configured = await harness.client.put(
        f"/api/v1/team-workspaces/{team_id}/board/configuration",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "expectedVersion": 0,
            "wipLimits": {"READY": 1, "IN_PROGRESS": 1},
        },
    )
    assert configured.status_code == 200
    assert configured.json()["version"] == 1

    moved = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/board/moves",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "itemType": "WORK_PACKAGE",
            "itemId": package_id,
            "target": "READY",
            "expectedVersion": package["version"],
            "reason": "The package is sufficiently defined to begin delivery.",
        },
    )
    assert moved.status_code == 200, moved.text
    package = moved.json()
    assert package["status"] == "READY"

    updated_body = package_command(
        grant_id,
        owner_id,
        contributor_id,
        iterationId=iteration_id,
        expectedVersion=package["version"],
        priority="URGENT",
        remainingEffortMinutes=180,
    )
    updated = await harness.client.put(
        f"/api/v1/team-workspaces/{team_id}/packages/{package_id}",
        headers=harness.mutation_headers(),
        json=updated_body,
    )
    assert updated.status_code == 200, updated.text
    package = updated.json()
    assert package["priority"] == "URGENT"

    starts_at = datetime.now(UTC) + timedelta(days=1)
    reserved = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/packages/{package_id}/reservations",
        params={"packageVersion": package["version"]},
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "userId": owner_id,
            "startsAt": starts_at.isoformat(),
            "endsAt": (starts_at + timedelta(hours=2)).isoformat(),
            "reason": "Protected focus time for producing the customer product.",
        },
    )
    assert reserved.status_code == 200, reserved.text
    package = reserved.json()
    reservation = package["reservations"][0]
    assert reservation["minutes"] == 120

    async with harness.sessions() as session, session.begin():
        stored_package = await session.get(WorkPackage, UUID(package_id))
        assert stored_package is not None
        stored_package.status = WorkPackageStatus.DONE
    reservation_block = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/memberships/"
        f"{owner_membership['membershipId']}/end",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "expectedVersion": owner_membership["version"],
            "reason": "The reservation must be released before this roster change.",
        },
    )
    assert reservation_block.status_code == 409
    assert "capacity reservations" in reservation_block.json()["detail"]["message"]

    cancelled = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/packages/{package_id}/reservations/"
        f"{reservation['id']}/cancel",
        params={"packageVersion": package["version"]},
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "expectedVersion": reservation["version"],
            "reason": "The delivery plan changed after the team review meeting.",
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["reservations"][0]["status"] == "CANCELLED"

    iterations = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/iterations"
    )
    assert iterations.status_code == 200
    closed = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/iterations/{iteration_id}/close",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "expectedVersion": iteration.json()["version"],
            "completionSummary": "The pilot iteration delivered its agreed outcome.",
        },
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"


async def test_personal_saved_views_wip_and_exact_team_security(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    osg = await workspace(harness)
    team_id, grant_id = osg["teamId"], osg["grantId"]
    owner_id = str(await harness.user_id("admin11"))
    contributor_id = str(await harness.user_id("admin12"))

    view = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/board/saved-views",
        headers=harness.mutation_headers(),
        json={
            "name": "Urgent owned work",
            "filters": {
                "search": "",
                "columns": ["IN_PROGRESS"],
                "priorities": ["URGENT"],
                "ownerUserId": owner_id,
                "itemTypes": ["WORK_PACKAGE"],
                "dueBefore": None,
            },
        },
    )
    assert view.status_code == 200
    changed = await harness.client.put(
        f"/api/v1/team-workspaces/{team_id}/board/saved-views/{view.json()['id']}",
        headers=harness.mutation_headers(),
        json={
            "name": "My urgent packages",
            "filters": view.json()["filters"],
            "expectedVersion": view.json()["version"],
        },
    )
    assert changed.status_code == 200

    await harness.login("admin11")
    private_board = await harness.client.get(f"/api/v1/team-workspaces/{team_id}/board")
    assert private_board.status_code == 200
    assert private_board.json()["savedViews"] == []
    analyst_created = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/packages",
        headers=harness.mutation_headers(),
        json=package_command(None, owner_id, contributor_id),
    )
    assert analyst_created.status_code == 200, analyst_created.text
    package = analyst_created.json()

    own_move = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/packages/{package['id']}/move",
        headers=harness.mutation_headers(),
        json={
            "expectedVersion": package["version"],
            "target": "READY",
            "reason": "The analyst has completed the package planning details.",
        },
    )
    assert own_move.status_code == 200

    reassignment = await harness.client.put(
        f"/api/v1/team-workspaces/{team_id}/packages/{package['id']}",
        headers=harness.mutation_headers(),
        json=package_command(
            None,
            str(await harness.user_id("admin13")),
            contributor_id,
            expectedVersion=own_move.json()["version"],
        ),
    )
    assert reassignment.status_code == 404

    await harness.login("admin13")
    hidden = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/packages/{package['id']}"
    )
    assert hidden.status_code == 200
    denied_move = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/packages/{package['id']}/move",
        headers=harness.mutation_headers(),
        json={
            "expectedVersion": own_move.json()["version"],
            "target": "IN_PROGRESS",
            "reason": "A different analyst must not change an unassigned package.",
        },
    )
    assert denied_move.status_code == 404

    quartz_id = await harness.unit_id("QUARTZ_TEAM")
    cross_team = await harness.client.get(f"/api/v1/team-workspaces/{quartz_id}/board")
    assert cross_team.status_code == 404

    await workspace(harness)
    service_move = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/board/moves",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant_id,
            "itemType": "SERVICE_REQUEST",
            "itemId": str(uuid4()),
            "target": "IN_PROGRESS",
            "expectedVersion": 1,
            "reason": "Workflow requests need their named Camunda human action.",
        },
    )
    assert service_move.status_code == 409

    deleted = await harness.client.request(
        "DELETE",
        f"/api/v1/team-workspaces/{team_id}/board/saved-views/{view.json()['id']}",
        headers=harness.mutation_headers(),
        json={"expectedVersion": changed.json()["version"]},
    )
    assert deleted.status_code == 204
