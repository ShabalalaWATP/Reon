"""Administrator appointment of routing-unit Managers and Members."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from conftest import ApiHarness
from mist_service.management_models import ManagementAction, ManagementGrant
from mist_service.repositories.management import resolve_management_scope
from mist_service.team_models import TeamMembership, WorkspacePosition


async def test_administrator_can_appoint_and_remove_a_routing_manager(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin1")
    await harness.elevate()
    crioc_id = await harness.unit_id("CRIOC")
    created = await harness.client.post(
        "/api/v1/admin/users",
        json={
            "displayName": "Synthetic Routing Manager",
            "role": "INTAKE_TRIAGE",
            "scope": "CRIOC",
            "organisationUnitIds": [str(crioc_id)],
            "workspacePosition": "MANAGER",
        },
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    account = created.json()
    assert account["memberships"][0]["workspacePosition"] == "MANAGER"
    user_id = UUID(account["id"])
    async with harness.sessions() as session:
        membership = await session.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == user_id,
                TeamMembership.effective_until.is_(None),
            )
        )
        assert membership is not None
        assert membership.workspace_position is WorkspacePosition.MANAGER
        grants = list(
            await session.scalars(
                select(ManagementGrant).where(
                    ManagementGrant.subject_user_id == user_id,
                    ManagementGrant.revoked_at.is_(None),
                )
            )
        )
        assert len(grants) == 2
        exact = next(grant for grant in grants if not grant.include_descendants)
        statistics = next(grant for grant in grants if grant.include_descendants)
        assert (
            await resolve_management_scope(
                session,
                subject_user_id=user_id,
                grant_id=exact.id,
                target_unit_id=crioc_id,
                action=ManagementAction.ROSTER,
            )
        ) is not None
        assert (
            await resolve_management_scope(
                session,
                subject_user_id=user_id,
                grant_id=statistics.id,
                target_unit_id=crioc_id,
                action=ManagementAction.STATISTICS,
            )
        ) is not None

    changed = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={
            "displayName": "Synthetic Routing Member",
            "role": "INTAKE_TRIAGE",
            "scope": "CRIOC",
            "organisationUnitIds": [str(crioc_id)],
            "workspacePosition": "MEMBER",
            "expectedVersion": account["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["memberships"][0]["workspacePosition"] == "MEMBER"
    async with harness.sessions() as session:
        current = await session.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == user_id,
                TeamMembership.effective_until.is_(None),
            )
        )
        assert current is not None
        assert current.workspace_position is WorkspacePosition.MEMBER
        active_grant = await session.scalar(
            select(ManagementGrant.id).where(
                ManagementGrant.subject_user_id == user_id,
                ManagementGrant.revoked_at.is_(None),
            )
        )
        assert active_grant is None


async def test_administrator_cannot_invert_delivery_workspace_positions(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin1")
    await harness.elevate()
    ssg_id = await harness.unit_id("SSG_TEAM")
    for role, position in (
        ("DELIVERY_TEAM_LEAD", "MEMBER"),
        ("DELIVERY_SPECIALIST", "MANAGER"),
    ):
        response = await harness.client.post(
            "/api/v1/admin/users",
            json={
                "displayName": f"Invalid {role}",
                "role": role,
                "scope": "SSG Team",
                "organisationUnitIds": [str(ssg_id)],
                "workspacePosition": position,
            },
            headers=harness.mutation_headers(),
        )
        assert response.status_code == 409
