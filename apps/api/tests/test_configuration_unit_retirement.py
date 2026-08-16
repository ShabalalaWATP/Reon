"""Activating a configuration without a unit retires it for new requests only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from api_helpers import perform, submit_request
from configuration_support import (
    activate_second_configuration,
    draft_from_active,
    seed_configuration_context,
)
from conftest import ApiHarness
from mist_service.organisation_models import OrganisationUnit


async def test_activation_retires_a_dropped_team_but_keeps_pinned_routes(
    api_harness: ApiHarness,
) -> None:
    """A unit left out of the activated configuration is marked unconfigured
    and disappears from routing for requests pinned afterwards. A request
    pinned before still routes through it, because a pin fixes structure."""

    harness = api_harness
    cedar_id = await harness.unit_id("CEDAR_TEAM")
    ops_id = await harness.unit_id("ACSA_B_OPS")
    before = await submit_request(harness)

    async with harness.sessions() as session, session.begin():
        actors = await seed_configuration_context(session, baseline_already_seeded=True)
        payload = await draft_from_active(
            session,
            actors,
            label="Retire the synthetic Cedar team",
            effective_from=datetime.now(UTC) - timedelta(seconds=1),
        )
        payload = payload.model_copy(
            update={
                "units": [u for u in payload.units if u.unit_id != cedar_id],
                "edges": [e for e in payload.edges if e.child_unit_id != cedar_id],
                "candidate_groups": [
                    g for g in payload.candidate_groups if g.unit_id != cedar_id
                ],
            }
        )
        await activate_second_configuration(
            session, harness.settings, actors, payload=payload
        )

    async with harness.sessions() as session:
        cedar = await session.get(OrganisationUnit, cedar_id)
        assert cedar is not None
        assert cedar.is_configured is False

    await _to_allocation(harness)
    after = await submit_request(harness)
    await _to_allocation(harness)

    await harness.login("admin6")
    listed = await harness.client.get("/api/v1/work-items")
    assert listed.status_code == 200, listed.text
    by_request = {item["requestId"]: item for item in listed.json()["items"]}
    assert set(by_request) == {before, after}
    assert _team_ids(await _options(harness, by_request[before]), ops_id) >= {cedar_id}
    assert cedar_id not in _team_ids(await _options(harness, by_request[after]), ops_id)


async def _to_allocation(harness: ApiHarness) -> None:
    await perform(harness, "admin4", {"action": "progress", "priority": "LOW"})
    await perform(harness, "admin5", {"action": "send_to_allocation", "note": "Go."})


async def _options(harness: ApiHarness, item: dict[str, Any]) -> list[dict[str, Any]]:
    response = await harness.client.get(
        f"/api/v1/work-items/{item['id']}/routing-options"
    )
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


def _team_ids(items: list[dict[str, Any]], parent_id: UUID) -> set[UUID]:
    return {
        UUID(item["id"]) for item in items if item.get("parentId") == str(parent_id)
    }
