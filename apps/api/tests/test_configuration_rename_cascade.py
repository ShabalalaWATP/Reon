"""Activating a configuration that renames a unit carries the name to members."""

from __future__ import annotations

from typing import cast

from sqlalchemy import select

from conftest import ApiHarness
from mist_service.models import User
from test_configuration_api import _action, _draft_payload


async def _scope(harness: ApiHarness, username: str) -> str:
    async with harness.sessions() as session:
        user = await session.scalar(select(User).where(User.username == username))
        assert user is not None
        return user.scope


async def test_activated_rename_reaches_every_kind_of_member_scope(
    api_harness: ApiHarness,
) -> None:
    """A team rename follows every Manager and Analyst, because that scope
    authorises. A routing-pool rename follows only members whose display scope
    was the old name; a shared multi-unit scope is untouched."""

    harness = api_harness
    await harness.login("admin1")
    await harness.elevate()
    active = (await harness.client.get("/api/v1/admin/configuration/active")).json()
    template = cast(dict[str, object], active["workflowTemplate"])
    draft = _draft_payload(active, str(template["workflowDefinitionId"]))
    renames = {"CRIOC": "Northern Routing Centre", "SSG_TEAM": "Osprey Team"}
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
