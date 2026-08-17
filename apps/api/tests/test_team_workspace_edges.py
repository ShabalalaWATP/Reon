"""Negative, concurrency and administration edges for team workspaces."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select

from conftest import ApiHarness
from mist_service.errors import InvalidAdministrationChange
from mist_service.management_models import ManagementAction
from mist_service.models import User
from mist_service.organisation_models import (
    OrganisationKind,
    UserOrganisationMembership,
)
from mist_service.repositories.team_workspace_authority import (
    WorkspaceAuthority,
    workspace_views,
)
from mist_service.repositories.team_workspaces import (
    _merge_authority,
    _own_authority,
)
from mist_service.team_membership_admin import align_admin_team_membership
from mist_service.team_membership_seed import seed_team_membership_history
from mist_service.team_membership_sync import synchronise_due_team_memberships
from mist_service.team_models import TeamMembership, WorkspacePosition
from mist_service.team_workspace_views import _as_utc
from mist_service.workspace_workloads import active_work_counts


async def _access(harness: ApiHarness, username: str, team_code: str) -> dict:
    await harness.login(username)
    response = await harness.client.get("/api/v1/team-workspaces")
    team_id = str(await harness.unit_id(team_code))
    return next(item for item in response.json()["items"] if item["teamId"] == team_id)


async def _member(harness: ApiHarness, team_id: str, name: str) -> dict:
    response = await harness.client.get(f"/api/v1/team-workspaces/{team_id}/people")
    assert response.status_code == 200
    return next(
        item for item in response.json()["items"] if item["displayName"] == name
    )


async def test_roster_rejects_wrong_accounts_teams_grants_and_versions(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    ssg = await _access(harness, "admin8", "SSG_TEAM")
    lewis = await _member(harness, ssg["teamId"], "Lewis Ferguson")
    manager_id = await harness.user_id("admin8")
    existing = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/memberships",
        json={
            "grantId": ssg["grantId"],
            "analystId": lewis["accountId"],
            "reason": "This deliberately attempts to add an existing member.",
        },
        headers=harness.mutation_headers(),
    )
    assert existing.status_code == 409
    wrong_role = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/memberships",
        json={
            "grantId": ssg["grantId"],
            "analystId": str(manager_id),
            "reason": (
                "A Team Manager cannot be added through the Analyst roster action."
            ),
        },
        headers=harness.mutation_headers(),
    )
    assert wrong_role.status_code == 409
    missing = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/memberships",
        json={
            "grantId": ssg["grantId"],
            "analystId": str(uuid4()),
            "reason": "An unknown account must not disclose any roster information.",
        },
        headers=harness.mutation_headers(),
    )
    assert missing.status_code == 404
    stale = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/memberships/{lewis['membershipId']}/end",
        json={
            "grantId": ssg["grantId"],
            "expectedVersion": lewis["version"] + 1,
            "reason": "A stale membership version must lose the concurrent update.",
        },
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "STALE_VERSION"
    wrong_grant = await harness.client.get(
        f"/api/v1/team-workspaces/{ssg['teamId']}/eligible-analysts",
        params={"grantId": str(uuid4())},
    )
    assert wrong_grant.status_code == 404

    await harness.login("admin11")
    analyst_denied = await harness.client.get(
        f"/api/v1/team-workspaces/{ssg['teamId']}/eligible-analysts",
        params={"grantId": ssg["grantId"]},
    )
    assert analyst_denied.status_code == 404


async def test_transfer_validation_and_immediate_projection_change(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    ssg = await _access(harness, "admin8", "SSG_TEAM")
    lewis = await _member(harness, ssg["teamId"], "Lewis Ferguson")
    base = {
        "grantId": ssg["grantId"],
        "analystId": lewis["accountId"],
        "currentMembershipId": lewis["membershipId"],
        "expectedVersion": lewis["version"],
        "reason": "A valid-length synthetic transfer reason for boundary testing.",
    }
    same_team = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/transfers",
        json={
            **base,
            "effectiveFrom": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
        headers=harness.mutation_headers(),
    )
    assert same_team.status_code == 409

    quartz = await _access(harness, "admin23", "QUARTZ_TEAM")
    command = {**base, "grantId": quartz["grantId"]}
    past = await harness.client.post(
        f"/api/v1/team-workspaces/{quartz['teamId']}/transfers",
        json={
            **command,
            "effectiveFrom": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        },
        headers=harness.mutation_headers(),
    )
    assert past.status_code == 409
    distant = await harness.client.post(
        f"/api/v1/team-workspaces/{quartz['teamId']}/transfers",
        json={
            **command,
            "effectiveFrom": (datetime.now(UTC) + timedelta(days=367)).isoformat(),
        },
        headers=harness.mutation_headers(),
    )
    assert distant.status_code == 409
    naive = await harness.client.post(
        f"/api/v1/team-workspaces/{quartz['teamId']}/transfers",
        json={**command, "effectiveFrom": "2026-09-01T12:00:00"},
        headers=harness.mutation_headers(),
    )
    assert naive.status_code == 422
    immediate = await harness.client.post(
        f"/api/v1/team-workspaces/{quartz['teamId']}/transfers",
        json={**command, "effectiveFrom": datetime.now(UTC).isoformat()},
        headers=harness.mutation_headers(),
    )
    assert immediate.status_code == 200, immediate.text
    analyst_id = await harness.user_id("admin11")
    quartz_id = await harness.unit_id("QUARTZ_TEAM")
    async with harness.sessions() as session:
        projection = set(
            await session.scalars(
                select(UserOrganisationMembership.unit_id).where(
                    UserOrganisationMembership.user_id == analyst_id
                )
            )
        )
        assert projection == {quartz_id}


async def test_scheduled_transfer_blocks_second_schedule_and_admin_override(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    quartz = await _access(harness, "admin23", "QUARTZ_TEAM")
    eligible = await harness.client.get(
        f"/api/v1/team-workspaces/{quartz['teamId']}/eligible-analysts",
        params={"grantId": quartz["grantId"]},
    )
    nathan = next(
        item
        for item in eligible.json()["items"]
        if item["displayName"] == "Nathan Patterson"
    )
    future = datetime.now(UTC) + timedelta(days=10)
    first = await harness.client.post(
        f"/api/v1/team-workspaces/{quartz['teamId']}/transfers",
        json={
            "grantId": quartz["grantId"],
            "analystId": nathan["accountId"],
            "currentMembershipId": nathan["currentMembershipId"],
            "expectedVersion": nathan["currentMembershipVersion"],
            "effectiveFrom": future.isoformat(),
            "reason": "The first scheduled move owns the effective membership window.",
        },
        headers=harness.mutation_headers(),
    )
    assert first.status_code == 200
    cedar = await _access(harness, "admin21", "CEDAR_TEAM")
    second = await harness.client.post(
        f"/api/v1/team-workspaces/{cedar['teamId']}/transfers",
        json={
            "grantId": cedar["grantId"],
            "analystId": nathan["accountId"],
            "currentMembershipId": nathan["currentMembershipId"],
            "expectedVersion": nathan["currentMembershipVersion"] + 1,
            "effectiveFrom": (future + timedelta(days=1)).isoformat(),
            "reason": "A second schedule must not overlap the first scheduled move.",
        },
        headers=harness.mutation_headers(),
    )
    assert second.status_code == 409
    assert "scheduled move" in second.json()["detail"]["message"]

    analyst_id = await harness.user_id("admin12")
    admin_id = await harness.user_id("admin1")
    cedar_id = await harness.unit_id("CEDAR_TEAM")
    async with harness.sessions() as session, session.begin():
        analyst = await session.get(User, analyst_id)
        assert analyst is not None
        try:
            await align_admin_team_membership(
                session,
                user=analyst,
                next_team_id=cedar_id,
                actor_id=admin_id,
            )
        except InvalidAdministrationChange as error:
            assert "scheduled" in error.message
        else:
            raise AssertionError("a scheduled transfer must block an admin override")


async def test_admin_moves_preserve_timeline_and_small_helpers(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    cedar_id = await harness.unit_id("CEDAR_TEAM")
    quartz_id = await harness.unit_id("QUARTZ_TEAM")
    await harness.login("admin1")
    await harness.elevate()
    created = await harness.client.post(
        "/api/v1/admin/users",
        json={
            "displayName": "Synthetic Roster Analyst",
            "role": "DELIVERY_SPECIALIST",
            "scope": "Ignored for team accounts",
            "organisationUnitIds": [str(cedar_id)],
        },
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    account = created.json()
    unchanged = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={
            "displayName": "Synthetic Roster Analyst Renamed",
            "role": "DELIVERY_SPECIALIST",
            "scope": "Cedar Team",
            "organisationUnitIds": [str(cedar_id)],
            "expectedVersion": account["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert unchanged.status_code == 200
    moved = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={
            "displayName": "Synthetic Roster Analyst Renamed",
            "role": "DELIVERY_SPECIALIST",
            "scope": "Quartz Team",
            "organisationUnitIds": [str(quartz_id)],
            "expectedVersion": unchanged.json()["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert moved.status_code == 200, moved.text
    requester = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={
            "displayName": "Synthetic Roster Analyst Renamed",
            "role": "REQUESTER",
            "scope": "Synthetic Customer Area",
            "organisationUnitIds": [],
            "expectedVersion": moved.json()["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert requester.status_code == 200
    async with harness.sessions() as session:
        history = list(
            await session.scalars(
                select(TeamMembership)
                .where(TeamMembership.user_id == UUID(account["id"]))
                .order_by(TeamMembership.effective_from)
            )
        )
        assert [item.team_id for item in history] == [cedar_id, quartz_id]
        assert all(item.effective_until is not None for item in history)
        assert await active_work_counts(session, set()) == {}
        assert _as_utc(datetime.now(UTC)).tzinfo is UTC
        assert (
            await synchronise_due_team_memberships(
                session, datetime(2020, 1, 1, tzinfo=UTC)
            )
            == 0
        )
        await seed_team_membership_history(session, set(), {cedar_id})


def test_workspace_authority_helpers_preserve_role_specific_views() -> None:
    team = SimpleNamespace(id=uuid4())
    own_id, own = _own_authority((team, WorkspacePosition.MANAGER))
    assert own_id == team.id
    assert own.position is WorkspacePosition.MANAGER

    first_grant = SimpleNamespace(id=uuid4(), include_descendants=True)
    authority = _merge_authority({}, (first_grant, ManagementAction.STATISTICS, team))
    assert authority[team.id].grant_id == first_grant.id
    replacement = SimpleNamespace(id=uuid4(), include_descendants=False)
    _merge_authority(authority, (replacement, ManagementAction.BOARD, team))
    assert authority[team.id].grant_id == first_grant.id
    _merge_authority(authority, (replacement, ManagementAction.ROSTER, team))
    assert authority[team.id].grant_id == replacement.id
    assert authority[team.id].descendant_permissions == {ManagementAction.STATISTICS}

    assert "BOARD" in workspace_views(
        WorkspaceAuthority(
            team=SimpleNamespace(kind=OrganisationKind.TEAM),
            position=WorkspacePosition.MEMBER,
        )
    )
    assert "QUEUE" in workspace_views(
        WorkspaceAuthority(
            team=SimpleNamespace(kind=OrganisationKind.COMMAND),
            position=WorkspacePosition.MEMBER,
        )
    )
