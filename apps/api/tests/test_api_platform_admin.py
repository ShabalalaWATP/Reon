"""Behaviour tests for the bounded Platform Administrator API."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from conftest import ApiHarness
from istari_service.admin_audit import verify_admin_audit_integrity
from istari_service.admin_management_grants import STANDARD_MANAGER_GRANT_REASON
from istari_service.admin_models import AdminAuditEvent
from istari_service.management_models import ManagementGrant, ManagementGrantAction
from istari_service.models import Session, User
from istari_service.organisation_models import (
    OrganisationUnit,
    StaffingStatus,
    UserOrganisationMembership,
)


async def _admin_login(harness: ApiHarness) -> dict[str, object]:
    result = await harness.login("admin1")
    await harness.elevate()
    return result


async def _user(harness: ApiHarness, username: str) -> dict[str, object]:
    response = await harness.client.get(f"/api/v1/admin/users?query={username}")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    return next(
        item
        for item in items
        if item["username"] == username or item["displayName"] == username
    )


def _profile(
    *,
    name: str = "Synthetic Account",
    role: str = "REQUESTER",
    scope: str = "Requesting Area C",
    units: list[str] | None = None,
) -> dict[str, object]:
    return {
        "displayName": name,
        "role": role,
        "scope": scope,
        "organisationUnitIds": units or [],
    }


async def test_admin_access_search_shape_and_request_content_denial(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    denied = await harness.client.get("/api/v1/admin/users")
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "ADMINISTRATION_ACCESS_DENIED"

    await _admin_login(harness)
    response = await harness.client.get("/api/v1/admin/users?query=Andy%20Robertson")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert set(body["items"][0]) == {
        "id",
        "username",
        "email",
        "displayName",
        "role",
        "scope",
        "isActive",
        "version",
        "createdAt",
        "updatedAt",
        "memberships",
    }
    assert "passwordHash" not in response.text
    assert (await harness.client.get("/api/v1/requests")).status_code == 404
    assert (await harness.client.get(f"/api/v1/requests/{uuid4()}")).status_code == 404


async def test_admin_crud_contract_version_validation_and_session_revocation(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin_login(harness)
    mass_assignment = await harness.client.post(
        "/api/v1/admin/users",
        json={**_profile(), "username": "chosen", "password": "chosen"},
        headers=harness.mutation_headers(),
    )
    assert mass_assignment.status_code == 422

    created = await harness.client.post(
        "/api/v1/admin/users",
        json=_profile(name="  Fictional New User  ", scope="  Requesting Area C  "),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    account = created.json()
    assert account["username"] == "admin100"
    assert account["email"] == "admin100@istari.example.test"
    assert account["displayName"] == "Fictional New User"
    assert account["scope"] == "Requesting Area C"
    assert account["isActive"] is True
    assert account["version"] == 1
    assert account["memberships"] == []

    logged_in = await harness.login(account["username"])
    assert logged_in["user"]["role"] == "REQUESTER"
    target_cookie = harness.client.cookies.get(harness.settings.session_cookie_name)
    await _admin_login(harness)
    ssg_id = str(await harness.unit_id("SSG_TEAM"))
    updated = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={
            **_profile(
                name="Fictional Analyst",
                role="DELIVERY_SPECIALIST",
                scope="ignored by team policy",
                units=[ssg_id],
            ),
            "expectedVersion": account["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert updated.status_code == 200, updated.text
    changed = updated.json()
    assert changed["scope"] == "SSG Team"
    assert changed["version"] == 2
    assert changed["memberships"][0]["organisationUnitKind"] == "TEAM"

    stale = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={**_profile(), "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "STALE_VERSION"

    assert target_cookie is not None
    harness.client.cookies.clear()
    harness.client.cookies.set(
        harness.settings.session_cookie_name,
        target_cookie,
    )
    assert (await harness.client.get("/api/v1/auth/me")).status_code == 401


async def test_status_rules_staffing_and_local_only_gate(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin_login(harness)
    self_account = await _user(harness, "admin1")
    self_deactivate = await harness.client.patch(
        f"/api/v1/admin/users/{self_account['id']}/status",
        json={"isActive": False, "expectedVersion": self_account["version"]},
        headers=harness.mutation_headers(),
    )
    assert self_deactivate.status_code == 409

    analyst = await _user(harness, "Denis Law")
    team_id = UUID(analyst["memberships"][0]["organisationUnitId"])
    deactivated = await harness.client.patch(
        f"/api/v1/admin/users/{analyst['id']}/status",
        json={"isActive": False, "expectedVersion": analyst["version"]},
        headers=harness.mutation_headers(),
    )
    assert deactivated.status_code == 200
    async with harness.sessions() as session:
        team = await session.get(OrganisationUnit, team_id)
        assert team is not None
        assert team.staffing_status is StaffingStatus.UNSTAFFED

    reactivated = await harness.client.patch(
        f"/api/v1/admin/users/{analyst['id']}/status",
        json={
            "isActive": True,
            "expectedVersion": deactivated.json()["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert reactivated.status_code == 200
    async with harness.sessions() as session:
        team = await session.get(OrganisationUnit, team_id)
        assert team is not None
        assert team.staffing_status is StaffingStatus.STAFFED

    harness.settings.allow_demo_users = False
    unavailable = await harness.client.get("/api/v1/admin/users")
    assert unavailable.status_code == 404
    harness.settings.allow_demo_users = True


async def test_admin_managed_team_manager_receives_and_loses_exact_authority(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin_login(harness)
    team_id = await harness.unit_id("SSG_TEAM")
    created = await harness.client.post(
        "/api/v1/admin/users",
        json=_profile(
            name="Synthetic Grant Manager",
            role="DELIVERY_TEAM_LEAD",
            scope="ignored",
            units=[str(team_id)],
        ),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    account = created.json()
    async with harness.sessions() as session:
        grant = await session.scalar(
            select(ManagementGrant).where(
                ManagementGrant.subject_user_id == UUID(account["id"]),
                ManagementGrant.reason == STANDARD_MANAGER_GRANT_REASON,
                ManagementGrant.revoked_at.is_(None),
            )
        )
        assert grant is not None
        assert grant.root_unit_id == team_id
        assert not grant.include_descendants
        actions = set(
            await session.scalars(
                select(ManagementGrantAction.action).where(
                    ManagementGrantAction.grant_id == grant.id
                )
            )
        )
        assert actions
    updated = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={
            **_profile(
                name="Synthetic Grant Analyst",
                role="DELIVERY_SPECIALIST",
                scope="ignored",
                units=[str(team_id)],
            ),
            "expectedVersion": account["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert updated.status_code == 200, updated.text
    async with harness.sessions() as session:
        active = await session.scalar(
            select(ManagementGrant.id).where(
                ManagementGrant.subject_user_id == UUID(account["id"]),
                ManagementGrant.reason == STANDARD_MANAGER_GRANT_REASON,
                ManagementGrant.revoked_at.is_(None),
            )
        )
        assert active is None


async def test_membership_compatibility_missing_objects_and_audit_integrity(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin_login(harness)
    ssg_id = str(await harness.unit_id("SSG_TEAM"))
    invalid = await harness.client.post(
        "/api/v1/admin/users",
        json=_profile(role="REQUESTER", units=[ssg_id]),
        headers=harness.mutation_headers(),
    )
    assert invalid.status_code == 409
    two_teams = await harness.client.post(
        "/api/v1/admin/users",
        json=_profile(
            role="DELIVERY_TEAM_LEAD",
            units=[ssg_id, str(await harness.unit_id("CEDAR_TEAM"))],
        ),
        headers=harness.mutation_headers(),
    )
    assert two_teams.status_code == 409
    missing_unit = await harness.client.post(
        "/api/v1/admin/users",
        json=_profile(role="DELIVERY_SPECIALIST", units=[str(uuid4())]),
        headers=harness.mutation_headers(),
    )
    assert missing_unit.status_code == 409
    assert (
        await harness.client.get(f"/api/v1/admin/users/{uuid4()}")
    ).status_code == 404

    created = await harness.client.post(
        "/api/v1/admin/users",
        json=_profile(name="Audited Fictional Account"),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201

    async with harness.sessions() as session:
        assert await verify_admin_audit_integrity(session)
        event = await session.scalar(select(AdminAuditEvent))
        assert event is not None
        assert "password" not in event.summary.lower()
        event.summary = "tampered"
        await session.commit()
    async with harness.sessions() as session:
        assert not await verify_admin_audit_integrity(session)


async def test_security_changes_increment_credentials_and_memberships_are_real(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin_login(harness)
    target = await _user(harness, "admin2")
    async with harness.sessions() as session:
        before = await session.get(User, UUID(target["id"]))
        assert before is not None
        credential_version = before.credential_version
    response = await harness.client.patch(
        f"/api/v1/admin/users/{target['id']}",
        json={
            **_profile(name=target["displayName"], scope="Requesting Area Z"),
            "expectedVersion": target["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200
    async with harness.sessions() as session:
        stored = await session.get(User, UUID(target["id"]))
        assert stored is not None
        assert stored.credential_version == credential_version + 1
        memberships = list(
            await session.scalars(
                select(UserOrganisationMembership).where(
                    UserOrganisationMembership.user_id == stored.id
                )
            )
        )
        assert memberships == []
        sessions = list(
            await session.scalars(select(Session).where(Session.user_id == stored.id))
        )
        assert all(item.revoked_at is not None for item in sessions)
