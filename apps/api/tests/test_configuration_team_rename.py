"""Stable team access across immutable configuration-name pins."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_helpers import perform, reach_delivery_work, submit_request
from configuration_support import (
    activate_second_configuration,
    draft_from_active,
    seed_configuration_context,
)
from conftest import ApiHarness
from mist_service.configuration_models import RequestConfigurationPin
from mist_service.models import ServiceRequest, User
from mist_service.organisation_models import RequestRouteSelection


async def test_configured_team_rename_preserves_old_and_new_pin_access(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    team_id = await harness.unit_id("SSG_TEAM")
    old_id = UUID(await submit_request(harness))

    async with harness.sessions() as session, session.begin():
        actors = await seed_configuration_context(
            session,
            baseline_already_seeded=True,
        )
        payload = await draft_from_active(
            session,
            actors,
            label="Rename the synthetic delivery team",
            effective_from=datetime.now(UTC) - timedelta(seconds=1),
        )
        payload = payload.model_copy(
            update={
                "units": [
                    unit.model_copy(update={"name": "SSG Service Team"})
                    if unit.unit_id == team_id
                    else unit
                    for unit in payload.units
                ]
            }
        )
        activated = await activate_second_configuration(
            session,
            harness.settings,
            actors,
            payload=payload,
        )

    await _route_and_assign(harness)
    new_id = UUID(await reach_delivery_work(harness))

    await harness.login("admin11")
    listed = await harness.client.get("/api/v1/work-items")
    assert listed.status_code == 200
    work_by_request = {UUID(item["requestId"]): item for item in listed.json()["items"]}
    assert set(work_by_request) == {old_id, new_id}
    assert work_by_request[old_id]["deliveryTeam"] == "OSG Team"
    assert work_by_request[new_id]["deliveryTeam"] == "SSG Service Team"

    old_detail = await harness.client.get(f"/api/v1/requests/{old_id}")
    new_detail = await harness.client.get(f"/api/v1/requests/{new_id}")
    assert old_detail.status_code == new_detail.status_code == 200
    assert old_detail.json()["assignedDeliveryTeam"] == "OSG Team"
    assert new_detail.json()["assignedDeliveryTeam"] == "SSG Service Team"
    async with harness.sessions() as session:
        versions = {
            request_id: (await session.get(ServiceRequest, request_id)).version  # type: ignore[union-attr]
            for request_id in (old_id, new_id)
        }
    package_ids: list[str] = []
    for request_id in (old_id, new_id):
        created = await harness.client.post(
            "/api/v1/product-packages",
            json={
                "requestId": str(request_id),
                "expectedVersion": versions[request_id],
                "idempotencyKey": str(uuid4()),
            },
            headers=harness.mutation_headers(),
        )
        assert created.status_code == 201, created.text
        package_ids.append(created.json()["id"])
    await harness.login("admin8")
    for package_id in package_ids:
        review = await harness.client.get(f"/api/v1/product-packages/{package_id}")
        assert review.status_code == 200, review.text

    async with harness.sessions() as session:
        old_request = await session.get(ServiceRequest, old_id)
        new_request = await session.get(ServiceRequest, new_id)
        old_pin = await _pin(session, old_id)
        new_pin = await _pin(session, new_id)
        assert old_request is not None and new_request is not None
        assert old_request.assigned_delivery_team_id == team_id
        assert new_request.assigned_delivery_team_id == team_id
        assert await _selected_team(session, old_id) == team_id
        assert await _selected_team(session, new_id) == team_id
        assert old_pin.configuration_version_id == activated.based_on_version_id
        assert new_pin.configuration_version_id == activated.id
        assert _pinned_team_name(old_pin, team_id) == "OSG Team"
        assert _pinned_team_name(new_pin, team_id) == "SSG Service Team"
        users = list(
            await session.scalars(
                select(User).where(User.username.in_(["admin8", "admin11"]))
            )
        )
        assert {user.scope for user in users} == {"SSG Service Team"}


async def test_direct_rename_is_blocked_for_configured_units(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin1")
    await harness.elevate()
    team_id = await harness.unit_id("SSG_TEAM")
    units = await harness.client.get("/api/v1/organisation/units")
    team = next(item for item in units.json()["items"] if item["id"] == str(team_id))
    response = await harness.client.patch(
        f"/api/v1/admin/organisation/units/{team_id}",
        json={"name": "Unsafe Direct Rename", "expectedVersion": team["version"]},
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 409
    assert "Configuration administration" in response.json()["detail"]["message"]


async def _route_and_assign(harness: ApiHarness) -> None:
    await perform(
        harness,
        "admin4",
        {"action": "progress", "priority": "MEDIUM"},
    )
    await perform(
        harness,
        "admin5",
        {"action": "send_to_allocation", "note": "Route confirmed."},
    )
    await perform(
        harness,
        "admin6",
        {"action": "allocate", "requiredCapabilities": ["Structured writing"]},
    )
    await perform(
        harness,
        "admin8",
        {
            "action": "assign",
            "specialistId": str(await harness.user_id("admin11")),
        },
    )


async def _pin(session: AsyncSession, request_id: UUID) -> RequestConfigurationPin:
    pin = await session.scalar(
        select(RequestConfigurationPin).where(
            RequestConfigurationPin.request_id == request_id
        )
    )
    assert pin is not None
    return pin


async def _selected_team(session: AsyncSession, request_id: UUID) -> UUID | None:
    return await session.scalar(
        select(RequestRouteSelection.unit_id).where(
            RequestRouteSelection.request_id == request_id,
            RequestRouteSelection.position == 3,
        )
    )


def _pinned_team_name(pin: RequestConfigurationPin, team_id: UUID) -> str:
    return next(
        item["name"]
        for item in pin.snapshot["organisation"]["units"]
        if item["unitId"] == str(team_id)
    )
