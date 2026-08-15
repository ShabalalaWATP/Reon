"""Exact-team workspace and effective roster lifecycle through the API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from conftest import ApiHarness, request_payload
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.organisation_models import (
    OrganisationUnit,
    StaffingStatus,
    UserOrganisationMembership,
)
from mist_service.schemas.requests import RequestCreate
from mist_service.team_membership_sync import synchronise_due_team_memberships
from mist_service.team_models import TeamActivityEvent


async def _workspace(harness: ApiHarness, username: str, team_code: str) -> dict:
    await harness.login(username)
    response = await harness.client.get("/api/v1/team-workspaces")
    assert response.status_code == 200, response.text
    team_id = str(await harness.unit_id(team_code))
    return next(item for item in response.json()["items"] if item["teamId"] == team_id)


async def _people(harness: ApiHarness, team_id: str) -> list[dict]:
    response = await harness.client.get(f"/api/v1/team-workspaces/{team_id}/people")
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_workspace_access_overview_people_activity_and_scope_boundaries(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    ssg = await _workspace(harness, "admin8", "SSG_TEAM")
    assert ssg["teamName"] == "SSG Team"
    assert ssg["grantId"]
    assert set(ssg["permissions"]) == {
        "STATISTICS",
        "ROSTER",
        "CALENDAR",
        "BOARD",
        "CAPACITY",
    }
    overview = await harness.client.get(f"/api/v1/team-workspaces/{ssg['teamId']}")
    assert overview.status_code == 200
    expected_measures = {
        "managerCount": 3,
        "analystCount": 7,
        "activeWorkCount": 0,
        "dueSoonCount": 0,
        "overdueCount": 0,
    }
    assert {key: overview.json()[key] for key in expected_measures} == expected_measures
    manager_people = await _people(harness, ssg["teamId"])
    assert len([item for item in manager_people if item["state"] == "CURRENT"]) == 10
    assert all(item["startReason"] for item in manager_people)
    activity = await harness.client.get(
        f"/api/v1/team-workspaces/{ssg['teamId']}/activity"
    )
    assert activity.status_code == 200
    assert activity.json() == {"items": []}

    analyst_ssg = await _workspace(harness, "admin11", "SSG_TEAM")
    assert analyst_ssg["permissions"] == []
    profile = await harness.client.patch(
        "/api/v1/profile",
        json={
            "skills": ["Research", "Data analysis"],
            "expectedVersion": 1,
        },
        headers=harness.mutation_headers(),
    )
    assert profile.status_code == 200
    analyst_people = await _people(harness, analyst_ssg["teamId"])
    assert all(item["startReason"] is None for item in analyst_people)
    lewis = next(
        item for item in analyst_people if item["displayName"] == "Lewis Ferguson"
    )
    assert lewis["skills"] == ["Research", "Data analysis"]
    quartz_id = await harness.unit_id("QUARTZ_TEAM")
    denied = await harness.client.get(f"/api/v1/team-workspaces/{quartz_id}/people")
    assert denied.status_code == 404

    await harness.login("admin5")
    routing_workspaces = await harness.client.get("/api/v1/team-workspaces")
    assert routing_workspaces.status_code == 200
    assert {item["teamCode"] for item in routing_workspaces.json()["items"]} == {
        "JOCK",
        "SYGOC",
        "MYGOC",
    }
    assert all(
        item["unitKind"] == "COMMAND"
        and item["workspacePosition"] == "MANAGER"
        and item["views"]
        == [
            "OVERVIEW",
            "QUEUE",
            "CALENDAR",
            "PEOPLE",
            "STATISTICS",
            "HANDOVER",
            "ACTIVITY",
        ]
        for item in routing_workspaces.json()["items"]
    )
    unknown = await harness.client.get(f"/api/v1/team-workspaces/{quartz_id}")
    assert unknown.status_code == 404


async def test_manager_can_end_and_add_existing_analyst_with_history(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    quartz = await _workspace(harness, "admin23", "QUARTZ_TEAM")
    quartz_people = await _people(harness, quartz["teamId"])
    alan = next(item for item in quartz_people if item["displayName"] == "Alan Hansen")
    invalid = await harness.client.post(
        f"/api/v1/team-workspaces/{quartz['teamId']}/memberships/{alan['membershipId']}/end",
        json={
            "grantId": quartz["grantId"],
            "expectedVersion": alan["version"],
            "reason": "short",
        },
        headers=harness.mutation_headers(),
    )
    assert invalid.status_code == 422
    ended = await harness.client.post(
        f"/api/v1/team-workspaces/{quartz['teamId']}/memberships/{alan['membershipId']}/end",
        json={
            "grantId": quartz["grantId"],
            "expectedVersion": alan["version"],
            "reason": "The Analyst is moving to support another delivery team.",
        },
        headers=harness.mutation_headers(),
    )
    assert ended.status_code == 200, ended.text
    ended_alan = next(
        item for item in ended.json()["items"] if item["displayName"] == "Alan Hansen"
    )
    assert ended_alan["state"] == "ENDED"
    assert ended_alan["endReason"].startswith("The Analyst")
    quartz_unit_id = await harness.unit_id("QUARTZ_TEAM")
    async with harness.sessions() as session:
        quartz_unit = await session.get(OrganisationUnit, quartz_unit_id)
        assert quartz_unit is not None
        assert quartz_unit.staffing_status is StaffingStatus.UNSTAFFED

    ssg = await _workspace(harness, "admin8", "SSG_TEAM")
    eligible = await harness.client.get(
        f"/api/v1/team-workspaces/{ssg['teamId']}/eligible-analysts",
        params={"grantId": ssg["grantId"]},
    )
    assert eligible.status_code == 200
    alan_option = next(
        item
        for item in eligible.json()["items"]
        if item["displayName"] == "Alan Hansen"
    )
    assert alan_option["currentTeamId"] is None
    added = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/memberships",
        json={
            "grantId": ssg["grantId"],
            "analystId": alan_option["accountId"],
            "reason": "The Analyst is joining SSG to balance delivery demand.",
        },
        headers=harness.mutation_headers(),
    )
    assert added.status_code == 200, added.text
    assert any(
        item["displayName"] == "Alan Hansen" and item["state"] == "CURRENT"
        for item in added.json()["items"]
    )
    stale = await harness.client.post(
        f"/api/v1/team-workspaces/{quartz['teamId']}/memberships/{alan['membershipId']}/end",
        json={
            "grantId": ssg["grantId"],
            "expectedVersion": alan["version"],
            "reason": "A deliberately invalid cross-team roster operation.",
        },
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 404
    assert (
        "Alan Hansen"
        in (
            await harness.client.get(
                f"/api/v1/team-workspaces/{ssg['teamId']}/activity"
            )
        ).text
    )


async def test_scheduled_transfer_has_one_winner_and_activates_projection(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    quartz = await _workspace(harness, "admin23", "QUARTZ_TEAM")
    eligible = await harness.client.get(
        f"/api/v1/team-workspaces/{quartz['teamId']}/eligible-analysts",
        params={"grantId": quartz["grantId"]},
    )
    lewis = next(
        item
        for item in eligible.json()["items"]
        if item["displayName"] == "Lewis Ferguson"
    )
    effective = datetime.now(UTC) + timedelta(days=7)
    command = {
        "grantId": quartz["grantId"],
        "analystId": lewis["accountId"],
        "currentMembershipId": lewis["currentMembershipId"],
        "expectedVersion": lewis["currentMembershipVersion"],
        "effectiveFrom": effective.isoformat(),
        "reason": (
            "The Analyst will transfer after completing the current planning cycle."
        ),
    }
    scheduled = await harness.client.post(
        f"/api/v1/team-workspaces/{quartz['teamId']}/transfers",
        json=command,
        headers=harness.mutation_headers(),
    )
    assert scheduled.status_code == 200, scheduled.text
    assert any(
        item["displayName"] == "Lewis Ferguson" and item["state"] == "SCHEDULED"
        for item in scheduled.json()["items"]
    )

    cedar = await _workspace(harness, "admin21", "CEDAR_TEAM")
    losing = await harness.client.post(
        f"/api/v1/team-workspaces/{cedar['teamId']}/transfers",
        json={**command, "grantId": cedar["grantId"]},
        headers=harness.mutation_headers(),
    )
    assert losing.status_code == 409
    assert losing.json()["detail"]["code"] == "STALE_VERSION"

    ssg_id = await harness.unit_id("SSG_TEAM")
    quartz_id = await harness.unit_id("QUARTZ_TEAM")
    analyst_id = await harness.user_id("admin11")
    async with harness.sessions() as session, session.begin():
        before = set(
            await session.scalars(
                select(UserOrganisationMembership.unit_id).where(
                    UserOrganisationMembership.user_id == analyst_id
                )
            )
        )
        assert before == {ssg_id}
        assert (
            await synchronise_due_team_memberships(
                session, effective + timedelta(seconds=1)
            )
            == 1
        )
    async with harness.sessions() as session:
        after = set(
            await session.scalars(
                select(UserOrganisationMembership.unit_id).where(
                    UserOrganisationMembership.user_id == analyst_id
                )
            )
        )
        assert after == {quartz_id}
        assert (
            await session.scalar(
                select(TeamActivityEvent.id).where(
                    TeamActivityEvent.subject_user_id == analyst_id,
                    TeamActivityEvent.type == "TRANSFER_ACTIVATED",
                )
            )
            is not None
        )


async def test_active_service_work_blocks_roster_removal_and_transfer(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    analyst_id = await harness.user_id("admin11")
    requester_id = await harness.user_id("admin2")
    async with harness.sessions() as session, session.begin():
        session.add(
            ServiceRequest(
                reference="SR-ROSTER-BLOCK-001",
                requester_id=requester_id,
                status=RequestStatus.IN_PROGRESS,
                current_owner="SSG Team",
                assigned_delivery_team="SSG Team",
                assigned_specialist_id=analyst_id,
                **RequestCreate.model_validate(request_payload()).model_dump(),
            )
        )
    ssg = await _workspace(harness, "admin8", "SSG_TEAM")
    lewis = next(
        item
        for item in await _people(harness, ssg["teamId"])
        if item["displayName"] == "Lewis Ferguson"
    )
    blocked_end = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/memberships/{lewis['membershipId']}/end",
        json={
            "grantId": ssg["grantId"],
            "expectedVersion": lewis["version"],
            "reason": "Attempting to move an Analyst who still owns active work.",
        },
        headers=harness.mutation_headers(),
    )
    assert blocked_end.status_code == 409
    assert "active service work" in blocked_end.json()["detail"]["message"]

    quartz = await _workspace(harness, "admin23", "QUARTZ_TEAM")
    blocked_transfer = await harness.client.post(
        f"/api/v1/team-workspaces/{quartz['teamId']}/transfers",
        json={
            "grantId": quartz["grantId"],
            "analystId": str(analyst_id),
            "currentMembershipId": lewis["membershipId"],
            "expectedVersion": lewis["version"],
            "effectiveFrom": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "reason": (
                "Attempting a transfer while active service work remains assigned."
            ),
        },
        headers=harness.mutation_headers(),
    )
    assert blocked_transfer.status_code == 409
