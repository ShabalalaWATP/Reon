"""Activated configuration is operational for newly pinned requests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from api_helpers import current_item, submit_request
from configuration_support import (
    activate_second_configuration,
    draft_from_active,
    seed_configuration_context,
)
from conftest import ApiHarness
from mist_service.configuration_models import RequestConfigurationPin
from mist_service.configuration_types import CandidateGroupPurpose
from mist_service.management_models import OrganisationClosure
from mist_service.models import ServiceRequest
from mist_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    StaffingStatus,
)
from mist_service.organisation_seed import organisation_id
from mist_service.schemas.configuration import (
    CandidateGroupInput,
    HierarchyEdgeInput,
    UnitRevisionInput,
)
from mist_service.workflow.variables import completion_variables


async def test_activation_materialises_staffs_and_routes_new_team_from_pin(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    new_team_id = uuid4()
    effective_from = datetime.now(UTC) - timedelta(seconds=1)
    async with harness.sessions() as session, session.begin():
        actors = await seed_configuration_context(
            session,
            baseline_already_seeded=True,
        )
        payload = await draft_from_active(
            session,
            actors,
            label="Add a synthetic routable team",
            effective_from=effective_from,
        )
        payload = payload.model_copy(
            update={
                "units": [
                    *payload.units,
                    UnitRevisionInput(
                        unit_id=new_team_id,
                        code="SYNTHETIC_TEAM",
                        name="Synthetic Team",
                        kind=OrganisationKind.TEAM,
                        effective_from=effective_from,
                        routing_enabled=True,
                        minimum_managers=1,
                        minimum_analysts=1,
                    ),
                ],
                "edges": [
                    *payload.edges,
                    HierarchyEdgeInput(
                        parent_unit_id=organisation_id("NIMBUS_OPS"),
                        child_unit_id=new_team_id,
                        effective_from=effective_from,
                    ),
                ],
                "candidate_groups": [
                    *payload.candidate_groups,
                    CandidateGroupInput(
                        unit_id=new_team_id,
                        purpose=CandidateGroupPurpose.MANAGER,
                        candidate_group="synthetic-team-managers",
                    ),
                    CandidateGroupInput(
                        unit_id=new_team_id,
                        purpose=CandidateGroupPurpose.ANALYST,
                        candidate_group="synthetic-team-analysts",
                    ),
                ],
            }
        )
        activated = await activate_second_configuration(
            session,
            harness.settings,
            actors,
            payload=payload,
        )
        materialised = await session.get(OrganisationUnit, new_team_id)
        assert materialised is not None
        assert materialised.parent_id == organisation_id("NIMBUS_OPS")
        assert materialised.staffing_status is StaffingStatus.UNSTAFFED
        closure = list(
            await session.scalars(
                select(OrganisationClosure).where(
                    OrganisationClosure.descendant_id == new_team_id
                )
            )
        )
        assert any(row.ancestor_id == new_team_id and row.depth == 0 for row in closure)
        assert any(
            row.ancestor_id == organisation_id("NIMBUS_OPS") and row.depth == 1
            for row in closure
        )

    await harness.login("admin2")
    visible = await harness.client.get("/api/v1/organisation/units")
    assert visible.status_code == 404
    assert str(new_team_id) not in visible.text

    await harness.login("admin4")
    visible = await harness.client.get("/api/v1/organisation/units")
    assert visible.status_code == 200
    assert any(item["id"] == str(new_team_id) for item in visible.json()["items"])

    await harness.login("admin1")
    await harness.elevate()
    lead = await _create_team_user(
        harness,
        new_team_id,
        name="Synthetic Team Lead",
        role="DELIVERY_TEAM_LEAD",
    )
    await _create_team_user(
        harness,
        new_team_id,
        name="Synthetic Team Specialist",
        role="DELIVERY_SPECIALIST",
    )
    async with harness.sessions() as session:
        staffed = await session.get(OrganisationUnit, new_team_id)
        assert staffed is not None
        assert staffed.staffing_status is StaffingStatus.STAFFED

    request_id = UUID(await submit_request(harness))
    async with harness.sessions() as session, session.begin():
        pin = await session.scalar(
            select(RequestConfigurationPin).where(
                RequestConfigurationPin.request_id == request_id
            )
        )
        live_team = await session.get(OrganisationUnit, new_team_id)
        assert pin is not None and live_team is not None
        assert pin.configuration_version_id == activated.id
        pinned_team = next(
            item
            for item in pin.snapshot["organisation"]["units"]
            if item["unitId"] == str(new_team_id)
        )
        assert pinned_team["staffingStatus"] == "STAFFED"
        live_team.name = "Later Live Name"
        live_team.parent_id = organisation_id("PARALLAX_OPS")
        live_team.manager_candidate_group = "later-live-managers"
        live_team.analyst_candidate_group = "later-live-analysts"
        live_team.is_configured = False

    await harness.login("admin4")
    triage = await current_item(harness)
    await _complete(
        harness,
        triage["id"],
        {
            "action": "progress",
            "priority": "HIGH",
            "destinationUnitId": str(organisation_id("SYGOC")),
        },
    )
    await harness.login("admin5")
    coordination = await current_item(harness)
    await _complete(
        harness,
        coordination["id"],
        {
            "action": "send_to_allocation",
            "note": "Use the pinned operational route.",
            "destinationUnitId": str(organisation_id("NIMBUS_OPS")),
        },
    )
    await harness.login("admin6")
    allocation = await current_item(harness)
    options = await harness.client.get(
        f"/api/v1/work-items/{allocation['id']}/routing-options"
    )
    assert options.status_code == 200
    assert [item["name"] for item in options.json()["route"]] == [
        "JIOC",
        "SYGOC",
        "Nimbus Ops",
    ]
    option = next(
        item for item in options.json()["items"] if item["id"] == str(new_team_id)
    )
    # Structure, staffing and candidate groups come from the pin; only the
    # display name follows the live unit.
    assert option["name"] == "Later Live Name"
    assert option["staffingStatus"] == "STAFFED"
    await _complete(
        harness,
        allocation["id"],
        {
            "action": "allocate",
            "destinationUnitId": str(new_team_id),
            "requiredCapabilities": ["Structured analysis"],
        },
    )

    variables = completion_variables(harness.workflow.completion_commands[2])
    assert variables["selectedTeamManagerCandidateGroup"] == ["synthetic-team-managers"]
    assert variables["selectedTeamAnalystCandidateGroup"] == ["synthetic-team-analysts"]
    async with harness.sessions() as session:
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        assert request.assigned_delivery_team == "Later Live Name"
        assert request.awaiting_team_staffing is False

    await harness.login(str(lead["username"]))
    work = await harness.client.get("/api/v1/work-items")
    assert work.status_code == 200
    assert len(work.json()["items"]) == 1


async def _create_team_user(
    harness: ApiHarness,
    team_id: UUID,
    *,
    name: str,
    role: str,
) -> dict[str, object]:
    response = await harness.client.post(
        "/api/v1/admin/users",
        json={
            "displayName": name,
            "role": role,
            "scope": "Synthetic Team",
            "organisationUnitIds": [str(team_id)],
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _complete(
    harness: ApiHarness,
    work_id: str,
    payload: dict[str, object],
) -> None:
    response = await harness.client.post(
        f"/api/v1/work-items/{work_id}/complete",
        json=payload,
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
