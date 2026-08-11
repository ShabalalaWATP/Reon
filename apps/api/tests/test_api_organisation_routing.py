"""Organisation routing, team ownership and tracking security behaviour."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

from api_helpers import current_item, submit_request
from conftest import ApiHarness, request_payload
from istari_service.models import (
    ServiceRequest,
    UserRole,
    WorkflowTaskStatus,
)
from istari_service.models import WorkflowTask as StoredWorkflowTask
from istari_service.team_models import TeamMembership
from istari_service.workflow.variables import completion_variables


async def _workspace(harness: ApiHarness, work_id: str) -> dict[str, Any]:
    response = await harness.client.get(f"/api/v1/work-items/{work_id}/routing-options")
    assert response.status_code == 200, response.text
    return response.json()


async def _options(harness: ApiHarness, work_id: str) -> list[dict[str, Any]]:
    return (await _workspace(harness, work_id))["items"]


async def _complete(
    harness: ApiHarness,
    work_id: str,
    payload: dict[str, Any],
    *,
    expected_status: int = 200,
) -> None:
    response = await harness.client.post(
        f"/api/v1/work-items/{work_id}/complete",
        json=payload,
        headers=harness.mutation_headers(),
    )
    assert response.status_code == expected_status, response.text


async def test_alternative_route_is_exact_and_uses_own_team_without_fallback(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await submit_request(harness)

    await harness.login("admin4")
    triage = await current_item(harness)
    command_workspace = await _workspace(harness, triage["id"])
    assert [(unit["name"], unit["code"]) for unit in command_workspace["route"]] == [
        ("CRIOC", "CRIOC")
    ]
    command_options = command_workspace["items"]
    assert [option["code"] for option in command_options] == [
        "JOCK",
        "SYGOC",
        "MYGOC",
    ]
    await _complete(
        harness,
        triage["id"],
        {
            "action": "progress",
            "priority": "HIGH",
            "destinationUnitId": str(await harness.unit_id("NIMBUS_OPS")),
        },
        expected_status=409,
    )
    sygoc_id = await harness.unit_id("SYGOC")
    await _complete(
        harness,
        triage["id"],
        {
            "action": "progress",
            "priority": "HIGH",
            "destinationUnitId": str(sygoc_id),
        },
    )

    await harness.login("admin5")
    command = await current_item(harness)
    ops_workspace = await _workspace(harness, command["id"])
    assert [unit["code"] for unit in ops_workspace["route"]] == ["CRIOC", "SYGOC"]
    ops_options = ops_workspace["items"]
    assert [option["code"] for option in ops_options] == [
        "NIMBUS_OPS",
        "PARALLAX_OPS",
        "HORIZON_OPS",
    ]
    await _complete(
        harness,
        command["id"],
        {
            "action": "send_to_allocation",
            "destinationUnitId": str(await harness.unit_id("AURORA_OPS")),
            "note": "Incorrect branch test.",
        },
        expected_status=409,
    )
    nimbus_id = await harness.unit_id("NIMBUS_OPS")
    await _complete(
        harness,
        command["id"],
        {
            "action": "send_to_allocation",
            "destinationUnitId": str(nimbus_id),
            "note": "Route confirmed.",
        },
    )

    await harness.login("admin6")
    allocation = await current_item(harness)
    team_workspace = await _workspace(harness, allocation["id"])
    assert [unit["code"] for unit in team_workspace["route"]] == [
        "CRIOC",
        "SYGOC",
        "NIMBUS_OPS",
    ]
    team_options = team_workspace["items"]
    assert [(item["code"], item["staffingStatus"]) for item in team_options] == [
        ("BEACON_TEAM", "STAFFED"),
        ("SLATE_TEAM", "STAFFED"),
        ("ORCHARD_TEAM", "STAFFED"),
    ]
    beacon_id = await harness.unit_id("BEACON_TEAM")
    await _complete(
        harness,
        allocation["id"],
        {
            "action": "allocate",
            "destinationUnitId": str(beacon_id),
            "requiredCapabilities": ["Structured analysis"],
        },
    )

    variables = [
        completion_variables(command)
        for command in harness.workflow.completion_commands[:3]
    ]
    assert variables[0]["selectedCommandId"] == str(sygoc_id)
    assert variables[0]["selectedCommandCandidateGroup"] == ["sygoc-routing"]
    assert variables[1]["selectedOpsId"] == str(nimbus_id)
    assert variables[1]["selectedOpsCandidateGroup"] == ["nimbus-ops-routing"]
    assert variables[2]["selectedTeamId"] == str(beacon_id)
    assert variables[2]["selectedTeamManagerCandidateGroup"] == ["beacon-team-managers"]
    assert variables[2]["selectedTeamAnalystCandidateGroup"] == ["beacon-team-analysts"]

    await harness.login("admin7")
    tracking = await harness.client.get("/api/v1/tracked-requests")
    assert tracking.status_code == 200
    tracked = tracking.json()["items"][0]
    assert set(tracked) == {
        "id",
        "reference",
        "title",
        "status",
        "currentOwner",
        "requiredBy",
        "createdAt",
        "updatedAt",
        "route",
        "awaitingTeamStaffing",
    }
    assert tracked["title"] == request_payload()["title"]
    assert tracked["currentOwner"] == "Team Manager"
    assert tracked["awaitingTeamStaffing"] is False
    assert [unit["name"] for unit in tracked["route"]] == [
        "CRIOC",
        "SYGOC",
        "Nimbus Ops",
        "Beacon Team",
    ]
    tracked_detail = await harness.client.get(f"/api/v1/tracked-requests/{request_id}")
    assert tracked_detail.status_code == 200
    assert tracked_detail.json()["title"] == request_payload()["title"]
    assert tracked_detail.json()["description"] == request_payload()["description"]
    assert {
        "deliverable",
        "clarifications",
        "feedback",
        "availableActions",
    }.isdisjoint(tracked_detail.json())

    async with harness.sessions() as session:
        task = await session.scalar(
            select(StoredWorkflowTask).where(
                StoredWorkflowTask.request_id == UUID(request_id),
                StoredWorkflowTask.status == WorkflowTaskStatus.OPEN,
            )
        )
        request = await session.get(ServiceRequest, UUID(request_id))
        assert task is not None and request is not None
        assert task.candidate_role is UserRole.DELIVERY_TEAM_LEAD
        assert task.assignee_user_id is None
        assert request.assigned_delivery_team == "Beacon Team"
        assert request.awaiting_team_staffing is False

    await harness.login("admin8")
    assert (await harness.client.get("/api/v1/work-items")).json()["items"] == []
    denied = await harness.client.post(
        f"/api/v1/work-items/{task.id}/claim",
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 404
    assert (
        await harness.client.get(f"/api/v1/tracked-requests/{request_id}")
    ).status_code == 404

    await harness.login("admin37")
    beacon_items = (await harness.client.get("/api/v1/work-items")).json()["items"]
    assert [item["id"] for item in beacon_items] == [str(task.id)]

    await harness.login("admin2")
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert detail.json()["assignedDeliveryTeam"] == "Beacon Team"
    assert "SSG_TEAM" not in detail.text

    await harness.login("admin5")
    assert (
        len((await harness.client.get("/api/v1/tracked-requests")).json()["items"]) == 1
    )
    command_user_id = await harness.user_id("admin5")
    async with harness.sessions() as session, session.begin():
        await session.execute(
            delete(TeamMembership).where(
                TeamMembership.user_id == command_user_id,
                TeamMembership.team_id == sygoc_id,
            )
        )
    assert (await harness.client.get("/api/v1/tracked-requests")).json()["items"] == []


async def test_organisation_reference_data_is_authenticated_and_complete(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    unauthenticated = await harness.client.get("/api/v1/organisation/units")
    assert unauthenticated.status_code == 401
    await harness.login("admin2")
    response = await harness.client.get("/api/v1/organisation/units")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 40
    assert sum(item["staffingStatus"] == "STAFFED" for item in items) == 27
    assert next(item for item in items if item["code"] == "SSG_TEAM")["name"] == (
        "SSG Team"
    )
    assert all("candidateGroup" not in item for item in items)
