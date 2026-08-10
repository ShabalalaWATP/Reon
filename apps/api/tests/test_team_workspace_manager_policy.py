"""Defence-in-depth tests for Manager-only workspace roster changes."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from conftest import ApiHarness
from istari_service.management_models import (
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
)
from istari_service.team_models import TeamMembership, WorkspacePosition


async def test_member_cannot_use_a_misconfigured_roster_grant(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    member_id = await harness.user_id("admin75")
    administrator_id = await harness.user_id("admin1")
    jioc_id = await harness.unit_id("JIOC")
    async with harness.sessions() as session, session.begin():
        grant = ManagementGrant(
            subject_user_id=member_id,
            root_unit_id=jioc_id,
            include_descendants=False,
            effective_from=datetime.now(UTC) - timedelta(minutes=1),
            effective_until=None,
            granted_by_user_id=administrator_id,
            reason="Synthetic deliberately misconfigured roster authority.",
            supersedes_grant_id=None,
            revoked_at=None,
            revoked_by_user_id=None,
            revocation_reason=None,
            version=1,
        )
        session.add(grant)
        await session.flush()
        session.add(
            ManagementGrantAction(
                grant_id=grant.id,
                action=ManagementAction.ROSTER,
            )
        )
    await harness.login("admin75")
    workspace = (await harness.client.get("/api/v1/team-workspaces")).json()["items"]
    jioc = next(item for item in workspace if item["teamId"] == str(jioc_id))
    assert jioc["workspacePosition"] == "MEMBER"
    assert jioc["permissions"] == ["ROSTER"]
    people = await harness.client.get(f"/api/v1/team-workspaces/{jioc_id}/people")
    assert people.status_code == 200
    assert all(item["startReason"] is None for item in people.json()["items"])
    async with harness.sessions() as session:
        target = await session.scalar(
            select(TeamMembership).where(
                TeamMembership.team_id == jioc_id,
                TeamMembership.user_id != member_id,
                TeamMembership.workspace_position == WorkspacePosition.MEMBER,
                TeamMembership.effective_until.is_(None),
            )
        )
    assert target is not None
    response = await harness.client.post(
        f"/api/v1/team-workspaces/{jioc_id}/memberships/{target.id}/end",
        json={
            "grantId": str(grant.id),
            "expectedVersion": target.version,
            "reason": "A Member must not be able to end another membership.",
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 404
