"""Regression coverage for action-scoped workspace projections."""

from datetime import UTC, datetime, timedelta

from conftest import ApiHarness, request_payload
from mist_service.analytics_models import RequestAnalyticsFact
from mist_service.management_models import (
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
)
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.schemas.requests import RequestCreate


async def _grant(
    harness: ApiHarness,
    *,
    username: str,
    unit_code: str,
    action: ManagementAction,
    include_descendants: bool,
) -> ManagementGrant:
    subject_id = await harness.user_id(username)
    unit_id = await harness.unit_id(unit_code)
    administrator_id = await harness.user_id("admin1")
    async with harness.sessions() as session, session.begin():
        grant = ManagementGrant(
            subject_user_id=subject_id,
            root_unit_id=unit_id,
            include_descendants=include_descendants,
            effective_from=datetime.now(UTC) - timedelta(minutes=1),
            effective_until=None,
            granted_by_user_id=administrator_id,
            reason="Synthetic projection-specific workspace authority.",
        )
        session.add(grant)
        await session.flush()
        session.add(ManagementGrantAction(grant_id=grant.id, action=action))
        return grant


async def _workspace(harness: ApiHarness, username: str, unit_code: str) -> dict:
    await harness.login(username)
    unit_id = str(await harness.unit_id(unit_code))
    response = await harness.client.get("/api/v1/team-workspaces")
    assert response.status_code == 200
    return next(item for item in response.json()["items"] if item["teamId"] == unit_id)


async def _calendar(harness: ApiHarness, unit_id: str):
    return await harness.client.get(
        f"/api/v1/team-workspaces/{unit_id}/calendar",
        params={"from": "2026-01-01T00:00:00Z", "to": "2026-01-02T00:00:00Z"},
    )


async def test_grant_only_reads_require_the_matching_projection_action(
    api_harness: ApiHarness,
) -> None:
    grant = await _grant(
        api_harness,
        username="admin11",
        unit_code="CRIOC",
        action=ManagementAction.CALENDAR,
        include_descendants=False,
    )
    access = await _workspace(api_harness, "admin11", "CRIOC")

    assert access["workspacePosition"] is None
    assert access["grantId"] == str(grant.id)
    assert access["views"] == ["OVERVIEW", "CALENDAR", "HANDOVER"]
    assert (await _calendar(api_harness, access["teamId"])).status_code == 200
    for suffix in ("people", "activity", "board"):
        response = await api_harness.client.get(
            f"/api/v1/team-workspaces/{access['teamId']}/{suffix}"
        )
        assert response.status_code == 404


async def test_direct_team_membership_retains_ordinary_projection_reads(
    api_harness: ApiHarness,
) -> None:
    access = await _workspace(api_harness, "admin11", "SSG_TEAM")

    assert access["permissions"] == []
    assert set(access["views"]) == {
        "OVERVIEW",
        "BOARD",
        "CALENDAR",
        "PEOPLE",
        "PLANNING",
        "HANDOVER",
        "ACTIVITY",
    }
    assert (await _calendar(api_harness, access["teamId"])).status_code == 200
    for suffix in ("people", "activity", "board"):
        response = await api_harness.client.get(
            f"/api/v1/team-workspaces/{access['teamId']}/{suffix}"
        )
        assert response.status_code == 200


async def test_workload_counts_require_descendant_statistics_authority(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    crioc_id = await harness.unit_id("CRIOC")
    ssg_id = await harness.unit_id("SSG_TEAM")
    requester_id = await harness.user_id("admin2")
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        request = ServiceRequest(
            reference="SR-WORKSPACE-SCOPE-001",
            requester_id=requester_id,
            status=RequestStatus.IN_PROGRESS,
            current_owner="OSG Team",
            assigned_delivery_team="OSG Team",
            **RequestCreate.model_validate(request_payload()).model_dump(),
        )
        session.add(request)
        await session.flush()
        session.add(
            RequestAnalyticsFact(
                request_id=request.id,
                root_unit_id=crioc_id,
                command_unit_id=crioc_id,
                ops_unit_id=None,
                team_unit_id=ssg_id,
                received_at=now,
                required_by=now.date() + timedelta(days=1),
                current_status=RequestStatus.IN_PROGRESS,
                last_transition_at=now,
                completed_at=None,
                closed_at=None,
                released_at=None,
                projected_at=now,
            )
        )

    routing_member = await _workspace(harness, "admin75", "CRIOC")
    member_overview = await harness.client.get(
        f"/api/v1/team-workspaces/{routing_member['teamId']}"
    )
    assert member_overview.status_code == 200
    assert member_overview.json()["workloadVisible"] is False
    assert member_overview.json()["activeWorkCount"] == 0

    descendant_statistics = await _workspace(harness, "admin15", "CRIOC")
    assert descendant_statistics["views"] == [
        "OVERVIEW",
        "STATISTICS",
        "HANDOVER",
    ]
    descendant_overview = await harness.client.get(
        f"/api/v1/team-workspaces/{descendant_statistics['teamId']}"
    )
    assert descendant_overview.json()["workloadVisible"] is True
    assert descendant_overview.json()["activeWorkCount"] == 1

    await _grant(
        harness,
        username="admin11",
        unit_code="CRIOC",
        action=ManagementAction.STATISTICS,
        include_descendants=False,
    )
    exact_statistics = await _workspace(harness, "admin11", "CRIOC")
    exact_overview = await harness.client.get(
        f"/api/v1/team-workspaces/{exact_statistics['teamId']}"
    )
    assert exact_overview.json()["workloadVisible"] is False
    assert exact_overview.json()["activeWorkCount"] == 0
