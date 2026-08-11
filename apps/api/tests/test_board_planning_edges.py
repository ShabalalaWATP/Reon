"""Concurrency, dependency, WIP and authorisation edges for team planning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from conftest import ApiHarness


def package_body(grant: str | None, owner: str, contributor: str) -> dict[str, Any]:
    return {
        "grantId": grant,
        "title": "Synthetic package for boundary testing",
        "description": "A complete fictional package used to exercise workflow edges.",
        "ownerUserId": owner,
        "contributorIds": [contributor],
        "estimatePoints": 3,
        "remainingEffortMinutes": 120,
        "dueOn": (datetime.now(UTC).date() + timedelta(days=7)).isoformat(),
        "priority": "MEDIUM",
        "blockers": "There are no known blockers for this synthetic package.",
        "acceptanceCriteria": "Every named synthetic acceptance point is satisfied.",
        "linkedRequestId": None,
        "dependencyIds": [],
        "iterationId": None,
    }


async def manager_context(harness: ApiHarness) -> tuple[str, str, str, str]:
    await harness.login("admin8")
    response = await harness.client.get("/api/v1/team-workspaces")
    ssg_id = str(await harness.unit_id("SSG_TEAM"))
    workspace = next(
        item for item in response.json()["items"] if item["teamId"] == ssg_id
    )
    return (
        ssg_id,
        workspace["grantId"],
        str(await harness.user_id("admin11")),
        str(await harness.user_id("admin12")),
    )


async def create_package(
    harness: ApiHarness, team: str, body: dict[str, Any]
) -> dict[str, Any]:
    response = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/packages",
        headers=harness.mutation_headers(),
        json=body,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def move(
    harness: ApiHarness,
    team: str,
    package: dict[str, Any],
    target: str,
    grant: str | None,
) -> Any:
    return await harness.client.post(
        f"/api/v1/team-workspaces/{team}/packages/{package['id']}/move",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant,
            "expectedVersion": package["version"],
            "target": target,
            "reason": "The team explicitly agreed this synthetic status change.",
        },
    )


async def test_wip_dependency_configuration_and_version_edges(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    team, grant, owner, contributor = await manager_context(harness)
    configured = await harness.client.put(
        f"/api/v1/team-workspaces/{team}/board/configuration",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant,
            "expectedVersion": 0,
            "wipLimits": {"READY": 1},
        },
    )
    assert configured.status_code == 200
    updated_config = await harness.client.put(
        f"/api/v1/team-workspaces/{team}/board/configuration",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant,
            "expectedVersion": 1,
            "wipLimits": {"READY": 1, "BLOCKED": 2},
        },
    )
    assert updated_config.json()["version"] == 2
    stale_config = await harness.client.put(
        f"/api/v1/team-workspaces/{team}/board/configuration",
        headers=harness.mutation_headers(),
        json={"grantId": grant, "expectedVersion": 1, "wipLimits": {}},
    )
    assert stale_config.status_code == 409

    first = await create_package(harness, team, package_body(grant, owner, contributor))
    second_body = package_body(grant, owner, contributor)
    second_body["title"] = "Second package for the WIP boundary"
    second = await create_package(harness, team, second_body)
    limited = await harness.client.get(
        f"/api/v1/team-workspaces/{team}/packages?limit=1"
    )
    assert len(limited.json()["items"]) == 1
    assert (
        await harness.client.get(f"/api/v1/team-workspaces/{team}/packages?limit=101")
    ).status_code == 422

    invalid_transition = await move(harness, team, first, "IN_PROGRESS", grant)
    assert invalid_transition.status_code == 409
    first_ready = await move(harness, team, first, "READY", grant)
    assert first_ready.status_code == 200
    wip_rejected = await move(harness, team, second, "READY", grant)
    assert wip_rejected.status_code == 409
    stale_move = await move(harness, team, first, "CANCELLED", grant)
    assert stale_move.status_code == 409

    self_dependency = package_body(grant, owner, contributor)
    self_dependency.update(
        expectedVersion=first_ready.json()["version"],
        dependencyIds=[first["id"]],
    )
    response = await harness.client.put(
        f"/api/v1/team-workspaces/{team}/packages/{first['id']}",
        headers=harness.mutation_headers(),
        json=self_dependency,
    )
    assert response.status_code == 409

    second_update = package_body(grant, owner, contributor)
    second_update.update(expectedVersion=second["version"], dependencyIds=[first["id"]])
    linked = await harness.client.put(
        f"/api/v1/team-workspaces/{team}/packages/{second['id']}",
        headers=harness.mutation_headers(),
        json=second_update,
    )
    assert linked.status_code == 200, linked.text
    first_update = package_body(grant, owner, contributor)
    first_update.update(
        expectedVersion=first_ready.json()["version"],
        dependencyIds=[second["id"]],
    )
    cycle = await harness.client.put(
        f"/api/v1/team-workspaces/{team}/packages/{first['id']}",
        headers=harness.mutation_headers(),
        json=first_update,
    )
    assert cycle.status_code == 409

    bad_dependency = package_body(grant, owner, contributor)
    bad_dependency["dependencyIds"] = [str(uuid4())]
    invalid_link = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/packages",
        headers=harness.mutation_headers(),
        json=bad_dependency,
    )
    assert invalid_link.status_code == 404
    missing = await harness.client.get(
        f"/api/v1/team-workspaces/{team}/packages/{uuid4()}"
    )
    assert missing.status_code == 404

    unavailable_move = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/board/moves",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant,
            "itemType": "WORK_PACKAGE",
            "itemId": first["id"],
            "target": "AWAITING_ASSIGNMENT",
            "expectedVersion": first_ready.json()["version"],
            "reason": "This column is reserved for authoritative service requests.",
        },
    )
    assert unavailable_move.status_code == 409


async def test_reservation_iteration_saved_view_and_grant_edges(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    team, grant, owner, contributor = await manager_context(harness)
    package = await create_package(
        harness, team, package_body(grant, owner, contributor)
    )
    start = datetime.now(UTC) + timedelta(days=2)
    reservation_body = {
        "grantId": grant,
        "userId": owner,
        "startsAt": start.isoformat(),
        "endsAt": (start + timedelta(hours=1)).isoformat(),
        "reason": "Reserve an hour for a synthetic focused delivery session.",
    }
    reserved = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/packages/{package['id']}/reservations",
        params={"packageVersion": package["version"]},
        headers=harness.mutation_headers(),
        json=reservation_body,
    )
    assert reserved.status_code == 200
    current = reserved.json()
    overlap = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/packages/{package['id']}/reservations",
        params={"packageVersion": current["version"]},
        headers=harness.mutation_headers(),
        json=reservation_body,
    )
    assert overlap.status_code == 409
    invalid_person = dict(reservation_body, userId=str(uuid4()))
    invalid_member = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/packages/{package['id']}/reservations",
        params={"packageVersion": current["version"]},
        headers=harness.mutation_headers(),
        json=invalid_person,
    )
    assert invalid_member.status_code == 404

    reservation = current["reservations"][0]
    cancel_url = (
        f"/api/v1/team-workspaces/{team}/packages/{package['id']}/reservations/"
        f"{reservation['id']}/cancel"
    )
    cancelled = await harness.client.post(
        cancel_url,
        params={"packageVersion": current["version"]},
        headers=harness.mutation_headers(),
        json={
            "grantId": grant,
            "expectedVersion": reservation["version"],
            "reason": "Cancel the reservation after replanning team availability.",
        },
    )
    assert cancelled.status_code == 200
    repeat_cancel = await harness.client.post(
        cancel_url,
        params={"packageVersion": cancelled.json()["version"]},
        headers=harness.mutation_headers(),
        json={
            "grantId": grant,
            "expectedVersion": 2,
            "reason": "A cancelled reservation cannot be cancelled a second time.",
        },
    )
    assert repeat_cancel.status_code == 409

    today = datetime.now(UTC).date()
    planned = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/iterations",
        headers=harness.mutation_headers(),
        json={
            "grantId": grant,
            "name": "Future synthetic iteration",
            "goal": "Demonstrate a planned iteration before its start date.",
            "startsOn": (today + timedelta(days=30)).isoformat(),
            "endsOn": (today + timedelta(days=44)).isoformat(),
        },
    )
    assert planned.json()["status"] == "PLANNED"
    close_body = {
        "grantId": grant,
        "expectedVersion": planned.json()["version"],
        "completionSummary": "The planned iteration was closed for boundary testing.",
    }
    closed = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/iterations/{planned.json()['id']}/close",
        headers=harness.mutation_headers(),
        json=close_body,
    )
    assert closed.status_code == 200
    close_body["expectedVersion"] = closed.json()["version"]
    repeat_close = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/iterations/{planned.json()['id']}/close",
        headers=harness.mutation_headers(),
        json=close_body,
    )
    assert repeat_close.status_code == 409
    missing_iteration = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/iterations/{uuid4()}/close",
        headers=harness.mutation_headers(),
        json={**close_body, "expectedVersion": 1},
    )
    assert missing_iteration.status_code == 404

    missing_grant = await harness.client.post(
        f"/api/v1/team-workspaces/{team}/packages",
        headers=harness.mutation_headers(),
        json=package_body(None, owner, contributor),
    )
    assert missing_grant.status_code == 404
    await harness.login("admin1")
    admin_denied = await harness.client.put(
        f"/api/v1/team-workspaces/{team}/board/configuration",
        headers=harness.mutation_headers(),
        json={"grantId": grant, "expectedVersion": 0, "wipLimits": {}},
    )
    assert admin_denied.status_code == 404
