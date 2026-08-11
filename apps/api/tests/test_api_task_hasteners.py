"""Exact-team Manager hasteners for assigned Analysts."""

from uuid import uuid4

from api_helpers import perform, reach_delivery_planning
from conftest import ApiHarness


async def test_any_exact_team_manager_can_hasten_one_or_all_assigned_analysts(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_planning(harness)
    lead_id = await harness.user_id("admin11")
    first_contributor_id = await harness.user_id("admin12")
    second_contributor_id = await harness.user_id("admin13")
    await perform(
        harness,
        "admin8",
        {
            "action": "assign",
            "specialistId": str(lead_id),
            "contributorIds": [
                str(first_contributor_id),
                str(second_contributor_id),
            ],
            "reason": "The Manager selected the accountable production team.",
        },
    )
    team_id = str(await harness.unit_id("SSG_TEAM"))
    await harness.login("admin9")

    all_response = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/requests/{request_id}/hasteners",
        json={
            "audience": "ALL_ASSIGNED",
            "message": "Please confirm progress before the team review this afternoon.",
        },
        headers=harness.mutation_headers(),
    )
    assert all_response.status_code == 200, all_response.text
    assert all_response.json()["senderDisplayName"] == "Kenny McLean"
    assert [
        (item["displayName"], item["assignmentRole"])
        for item in all_response.json()["recipients"]
    ] == [
        ("Lewis Ferguson", "LEAD"),
        ("Ben Doak", "CONTRIBUTOR"),
        ("Nathan Patterson", "CONTRIBUTOR"),
    ]

    one_response = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/requests/{request_id}/hasteners",
        json={
            "audience": "ONE_ASSIGNED",
            "recipientUserId": str(first_contributor_id),
            "message": "Please update your assigned contribution before the review.",
        },
        headers=harness.mutation_headers(),
    )
    assert one_response.status_code == 200, one_response.text
    assert [item["displayName"] for item in one_response.json()["recipients"]] == [
        "Nathan Patterson"
    ]

    unassigned_id = await harness.user_id("admin14")
    invalid_recipient = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/requests/{request_id}/hasteners",
        json={
            "audience": "ONE_ASSIGNED",
            "recipientUserId": str(unassigned_id),
            "message": "This deliberately targets an unassigned team member.",
        },
        headers=harness.mutation_headers(),
    )
    assert invalid_recipient.status_code == 409
    invalid_shape = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/requests/{request_id}/hasteners",
        json={
            "audience": "ALL_ASSIGNED",
            "recipientUserId": str(first_contributor_id),
            "message": "This deliberately supplies an invalid recipient shape.",
        },
        headers=harness.mutation_headers(),
    )
    assert invalid_shape.status_code == 422
    missing_recipient = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/requests/{request_id}/hasteners",
        json={
            "audience": "ONE_ASSIGNED",
            "message": "This deliberately omits the required named recipient.",
        },
        headers=harness.mutation_headers(),
    )
    unsafe_message = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/requests/{request_id}/hasteners",
        json={
            "audience": "ALL_ASSIGNED",
            "message": "This message contains a hidden mark.\u202e",
        },
        headers=harness.mutation_headers(),
    )
    missing_request = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/requests/{uuid4()}/hasteners",
        json={
            "audience": "ALL_ASSIGNED",
            "message": "This request does not exist within the exact team.",
        },
        headers=harness.mutation_headers(),
    )
    assert missing_recipient.status_code == unsafe_message.status_code == 422
    assert missing_request.status_code == 404

    await harness.login("admin2")
    customer_detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert customer_detail.status_code == 200
    assert all(
        item["type"] != "task_hastener" for item in customer_detail.json()["events"]
    )

    await harness.login("admin12")
    notifications = await harness.client.get(
        "/api/v1/me/notifications", params={"eventTypes": "TASK_HASTENER"}
    )
    assert notifications.status_code == 200, notifications.text
    assert len(notifications.json()["items"]) == 2
    assert all(
        item["deepLink"] == f"/teams/{team_id}/board?itemId={request_id}"
        for item in notifications.json()["items"]
    )
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert detail.status_code == 200
    hasteners = [
        item for item in detail.json()["events"] if item["type"] == "task_hastener"
    ]
    assert len(hasteners) == 2
    assert detail.json()["status"] == "IN_PROGRESS"
    assert detail.json()["assignedSpecialist"]["id"] == str(lead_id)

    denied = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/requests/{request_id}/hasteners",
        json={
            "audience": "ALL_ASSIGNED",
            "message": "An Analyst must not issue a Manager hastener.",
        },
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 404

    await perform(
        harness,
        "admin11",
        {
            "action": "submit",
            "deliverableTitle": "Synthetic summary",
            "deliverableText": "A sufficiently long fictional deliverable for review.",
        },
    )
    await harness.login("admin9")
    inactive_stage = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/requests/{request_id}/hasteners",
        json={
            "audience": "ALL_ASSIGNED",
            "message": "The production task is no longer active at this stage.",
        },
        headers=harness.mutation_headers(),
    )
    assert inactive_stage.status_code == 409


async def test_sibling_team_manager_cannot_hasten_another_teams_request(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_planning(harness)
    ssg_id = str(await harness.unit_id("SSG_TEAM"))
    await harness.login("admin23")
    response = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg_id}/requests/{request_id}/hasteners",
        json={
            "audience": "ALL_ASSIGNED",
            "message": "A sibling team must not see or alter this request.",
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 404
