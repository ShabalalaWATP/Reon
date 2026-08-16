"""Activating a configuration that renames a unit carries the name to members
and to the requests already assigned to a renamed team."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select

from api_helpers import current_item, reach_delivery_planning, submit_request
from conftest import ApiHarness
from mist_service.models import ServiceRequest, User
from test_configuration_api import _action, _draft_payload


async def _scope(harness: ApiHarness, username: str) -> str:
    async with harness.sessions() as session:
        user = await session.scalar(select(User).where(User.username == username))
        assert user is not None
        return user.scope


async def _assigned_team(harness: ApiHarness, request_id: str) -> str | None:
    async with harness.sessions() as session:
        request = await session.get(ServiceRequest, UUID(request_id))
        assert request is not None
        return request.assigned_delivery_team


async def test_activated_rename_reaches_every_kind_of_member_scope(
    api_harness: ApiHarness,
) -> None:
    """A team rename follows every Manager and Analyst, because that scope
    authorises, and follows the team-name snapshot on requests already routed
    to the team. A routing-pool rename follows only members whose display
    scope was the old name; a shared multi-unit scope is untouched. A request
    pinned before the rename offers routing destinations under their live
    names, because a pin fixes structure and not wording."""

    harness = api_harness
    assigned_id = await reach_delivery_planning(harness)
    assert await _assigned_team(harness, assigned_id) == "OSG Team"
    pinned_before = await submit_request(harness)
    await harness.login("admin1")
    await harness.elevate()
    active = (await harness.client.get("/api/v1/admin/configuration/active")).json()
    template = cast(dict[str, object], active["workflowTemplate"])
    draft = _draft_payload(active, str(template["workflowDefinitionId"]))
    renames = {
        "CRIOC": "Northern Routing Centre",
        "JOCK": "Digital Ops Centre",
        "SSG_TEAM": "Osprey Team",
    }
    for unit in cast(list[dict[str, object]], draft["units"]):
        if unit["code"] in renames:
            unit["name"] = renames[str(unit["code"])]

    # Before: the routing manager and a team member carry their units' current
    # names, while a coordination user carries a shared scope naming no unit.
    root_before = await _scope(harness, "admin4")
    team_before = await _scope(harness, "admin11")
    shared_before = await _scope(harness, "admin5")
    assert root_before not in renames.values()
    assert team_before not in renames.values()
    assert shared_before == "Shared request coordination"

    created = (
        await harness.client.post(
            "/api/v1/admin/configuration/versions",
            json=draft,
            headers=harness.mutation_headers(),
        )
    ).json()
    validated = await _action(
        harness, created["id"], "validate", {"expectedVersion": created["version"]}
    )
    submitted = await _action(
        harness,
        created["id"],
        "submit",
        {"expectedVersion": validated["version"], "reason": "Rename two units."},
    )
    await harness.login("admin73")
    await harness.elevate()
    approved = await _action(
        harness,
        created["id"],
        "approve",
        {"expectedVersion": submitted["version"], "reason": "Independent approval."},
    )
    activated = await _action(
        harness,
        created["id"],
        "activate",
        {"expectedVersion": approved["version"], "reason": "Activate the rename."},
    )
    assert activated["status"] == "ACTIVE"

    assert await _scope(harness, "admin4") == "Northern Routing Centre"
    assert await _scope(harness, "admin11") == "Osprey Team"
    assert await _scope(harness, "admin5") == shared_before
    assert await _assigned_team(harness, assigned_id) == "Osprey Team"

    await harness.login("admin4")
    item = await current_item(harness)
    assert item["requestId"] == pinned_before
    options = await harness.client.get(
        f"/api/v1/work-items/{item['id']}/routing-options"
    )
    assert options.status_code == 200, options.text
    names = {unit["code"]: unit["name"] for unit in options.json()["items"]}
    assert names["JOCK"] == "Digital Ops Centre"
