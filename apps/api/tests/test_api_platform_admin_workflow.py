"""Administration safeguards that interact with routed human work."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from conftest import ApiHarness, request_payload
from istari_service.models import ServiceRequest, User
from istari_service.organisation_models import OrganisationUnit


async def _claim_current(harness: ApiHarness) -> dict[str, object]:
    listed = await harness.client.get("/api/v1/work-items")
    assert listed.status_code == 200, listed.text
    item = listed.json()["items"][0]
    if item["assigneeId"] is None:
        claimed = await harness.client.post(
            f"/api/v1/work-items/{item['id']}/claim",
            headers=harness.mutation_headers(),
        )
        assert claimed.status_code == 200, claimed.text
        item = claimed.json()
    return item


async def _complete(
    harness: ApiHarness,
    username: str,
    payload: dict[str, object],
) -> None:
    await harness.login(username)
    item = await _claim_current(harness)
    response = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/complete",
        json=payload,
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text


async def _submit(harness: ApiHarness) -> str:
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201, response.text
    assert await harness.dispatch_start()
    return response.json()["id"]


async def _admin_user(harness: ApiHarness, username: str) -> dict[str, object]:
    response = await harness.client.get(f"/api/v1/admin/users?query={username}")
    assert response.status_code == 200
    return next(
        item for item in response.json()["items"] if item["username"] == username
    )


async def test_active_claimed_work_blocks_role_membership_and_deactivation(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _submit(harness)
    await harness.login("admin4")
    await _claim_current(harness)

    await harness.login("admin1")
    await harness.elevate()
    target = await _admin_user(harness, "admin4")
    blocked_status = await harness.client.patch(
        f"/api/v1/admin/users/{target['id']}/status",
        json={"isActive": False, "expectedVersion": target["version"]},
        headers=harness.mutation_headers(),
    )
    assert blocked_status.status_code == 409
    assert "active work" in blocked_status.json()["detail"]["message"]

    blocked_edit = await harness.client.patch(
        f"/api/v1/admin/users/{target['id']}",
        json={
            "displayName": target["displayName"],
            "role": "REQUESTER",
            "scope": "Requesting Area D",
            "organisationUnitIds": [],
            "expectedVersion": target["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert blocked_edit.status_code == 409


async def test_team_rename_preserves_stable_route_and_manager_access(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    harness.settings.configuration_admin_enabled = False
    request_id = await _submit(harness)
    await _complete(
        harness,
        "admin4",
        {
            "action": "progress",
            "priority": "MEDIUM",
            "destinationUnitId": str(await harness.unit_id("DIGOC")),
        },
    )
    await _complete(
        harness,
        "admin5",
        {
            "action": "send_to_allocation",
            "destinationUnitId": str(await harness.unit_id("NCGI_A_OPS")),
            "note": "Route confirmed.",
        },
    )
    await _complete(
        harness,
        "admin6",
        {
            "action": "allocate",
            "destinationUnitId": str(await harness.unit_id("OSG_TEAM")),
            "requiredCapabilities": ["Structured writing"],
        },
    )

    await harness.login("admin1")
    await harness.elevate()
    units = await harness.client.get("/api/v1/organisation/units")
    before = next(item for item in units.json()["items"] if item["code"] == "OSG_TEAM")
    stable = {
        "id": before["id"],
        "code": before["code"],
        "kind": before["kind"],
        "parentId": before["parentId"],
    }
    renamed = await harness.client.patch(
        f"/api/v1/admin/organisation/units/{before['id']}",
        json={
            "name": "  OSG Service Team  ",
            "expectedVersion": before["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "OSG Service Team"
    assert {key: renamed.json()[key] for key in stable} == stable
    assert renamed.json()["version"] == before["version"] + 1

    async with harness.sessions() as session:
        stored = await session.get(ServiceRequest, UUID(request_id))
        assert stored is not None
        assert stored.assigned_delivery_team == "OSG Service Team"
        unit = await session.get(OrganisationUnit, UUID(before["id"]))
        assert unit is not None
        assert unit.manager_candidate_group == "osg-team-managers"
        assert unit.analyst_candidate_group == "osg-team-analysts"
        manager = await session.scalar(select(User).where(User.username == "admin8"))
        assert manager is not None
        assert manager.scope == "OSG Service Team"

    await harness.login("admin8")
    work = await harness.client.get("/api/v1/work-items")
    assert work.status_code == 200
    assert len(work.json()["items"]) == 1


async def test_rename_conflict_stale_noop_and_csrf_safely(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    harness.settings.configuration_admin_enabled = False
    await harness.login("admin1")
    await harness.elevate()
    response = await harness.client.get("/api/v1/organisation/units")
    units = response.json()["items"]
    cedar = next(item for item in units if item["code"] == "CEDAR_TEAM")
    quartz = next(item for item in units if item["code"] == "QUARTZ_TEAM")

    missing_csrf = await harness.client.patch(
        f"/api/v1/admin/organisation/units/{cedar['id']}",
        json={"name": "Cedar Service Team", "expectedVersion": cedar["version"]},
    )
    assert missing_csrf.status_code == 403
    duplicate = await harness.client.patch(
        f"/api/v1/admin/organisation/units/{cedar['id']}",
        json={"name": quartz["name"].lower(), "expectedVersion": cedar["version"]},
        headers=harness.mutation_headers(),
    )
    assert duplicate.status_code == 409
    stale = await harness.client.patch(
        f"/api/v1/admin/organisation/units/{cedar['id']}",
        json={"name": "Cedar Service Team", "expectedVersion": 99},
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409
    noop = await harness.client.patch(
        f"/api/v1/admin/organisation/units/{cedar['id']}",
        json={"name": cedar["name"], "expectedVersion": cedar["version"]},
        headers=harness.mutation_headers(),
    )
    assert noop.status_code == 200
    assert noop.json()["version"] == cedar["version"]


async def test_administrator_self_role_removal_and_status_noop(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin1")
    await harness.elevate()
    target = await _admin_user(harness, "admin1")
    no_change = await harness.client.patch(
        f"/api/v1/admin/users/{target['id']}/status",
        json={"isActive": True, "expectedVersion": target["version"]},
        headers=harness.mutation_headers(),
    )
    assert no_change.status_code == 200
    remove_role = await harness.client.patch(
        f"/api/v1/admin/users/{target['id']}",
        json={
            "displayName": target["displayName"],
            "role": "REQUESTER",
            "scope": "Requesting Area E",
            "organisationUnitIds": [],
            "expectedVersion": target["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert remove_role.status_code == 409
