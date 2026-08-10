"""Every non-happy human route and loop remains explicit and authorised."""

from __future__ import annotations

from api_helpers import (
    current_item,
    perform,
    reach_allocation,
    reach_coordination,
    reach_delivery_planning,
    reach_lead_review,
    reach_quality_review,
    submit_request,
)
from conftest import ApiHarness


async def test_information_request_response_then_close(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await submit_request(harness)
    detail = await perform(
        harness,
        "admin4",
        {"action": "request_information", "reason": "Please add a source date."},
    )
    assert detail["status"] == "INFORMATION_REQUIRED"
    detail = await perform(
        harness,
        "admin2",
        {
            "action": "provide_information",
            "information": "The fictional source date is 1 August 2026.",
        },
    )
    assert detail["status"] == "TRIAGE_REVIEW"
    detail = await perform(
        harness,
        "admin7",
        {"action": "close", "reason": "The request is no longer required."},
    )
    assert detail["status"] == "CLOSED_NOT_PROGRESSED"

    await harness.login("admin2")
    feedback = await harness.client.post(
        f"/api/v1/requests/{request_id}/feedback",
        json={"rating": 3, "comments": "The request was closed."},
        headers=harness.mutation_headers(),
    )
    assert feedback.status_code == 409


async def test_requester_can_withdraw_when_information_is_requested(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await submit_request(harness)
    await perform(
        harness,
        "admin4",
        {"action": "request_information", "reason": "Clarification is required."},
    )
    detail = await perform(
        harness,
        "admin2",
        {"action": "withdraw", "reason": "The fictional need has ended."},
    )
    assert detail["status"] == "CANCELLED"


async def test_coordination_hold_resume_return_and_close(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await reach_coordination(harness)
    detail = await perform(
        harness,
        "admin5",
        {"action": "hold", "reason": "Awaiting a fictional dependency."},
    )
    assert detail["status"] == "ON_HOLD"
    detail = await perform(
        harness,
        "admin5",
        {"action": "resume", "note": "The fictional dependency is resolved."},
    )
    assert detail["status"] == "COORDINATION_REVIEW"
    detail = await perform(
        harness,
        "admin5",
        {"action": "return_to_triage", "reason": "Recheck the category."},
    )
    assert detail["status"] == "TRIAGE_REVIEW"

    await perform(
        harness,
        "admin4",
        {"action": "progress", "priority": "LOW"},
    )
    detail = await perform(
        harness,
        "admin5",
        {"action": "close", "reason": "Closed by human review."},
    )
    assert detail["status"] == "CLOSED_NOT_PROGRESSED"


async def test_hold_can_close_directly(api_harness: ApiHarness) -> None:
    harness = api_harness
    await reach_coordination(harness)
    await perform(
        harness,
        "admin5",
        {"action": "hold", "reason": "Awaiting a fictional dependency."},
    )
    detail = await perform(
        harness,
        "admin5",
        {"action": "close", "reason": "The dependency will not arrive."},
    )
    assert detail["status"] == "CLOSED_NOT_PROGRESSED"


async def test_allocation_and_planning_return_loops(api_harness: ApiHarness) -> None:
    harness = api_harness
    await reach_allocation(harness)
    detail = await perform(
        harness,
        "admin6",
        {"action": "return_to_coordination", "reason": "Clarify the target."},
    )
    assert detail["status"] == "COORDINATION_REVIEW"

    await perform(
        harness,
        "admin5",
        {"action": "send_to_allocation", "note": "Route confirmed."},
    )
    await perform(
        harness,
        "admin6",
        {
            "action": "allocate",
            "requiredCapabilities": ["Structured writing"],
        },
    )
    detail = await perform(
        harness,
        "admin8",
        {"action": "return_for_reallocation", "reason": "A different team is needed."},
    )
    assert detail["status"] == "ALLOCATION_REVIEW"


async def test_lead_and_quality_changes_create_rework_versions(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await reach_lead_review(harness)
    detail = await perform(
        harness,
        "admin8",
        {"action": "changes_required", "reason": "Add a clearer conclusion."},
    )
    assert detail["status"] == "REWORK_REQUIRED"
    await perform(
        harness,
        "admin11",
        {
            "action": "submit",
            "deliverableTitle": "Synthetic summary revision two",
            "deliverableText": (
                "A revised fictional deliverable with a clearer conclusion."
            ),
        },
    )
    await perform(harness, "admin8", {"action": "approve"})
    detail = await perform(
        harness,
        "admin15",
        {"action": "changes_required", "reason": "Correct a formatting issue."},
    )
    assert detail["status"] == "REWORK_REQUIRED"


async def test_invalid_action_and_wrong_team_are_rejected_before_engine(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await reach_delivery_planning(harness)
    await harness.login("admin8")
    item = await current_item(harness)
    wrong_specialist = await harness.user_id("admin15")
    response = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/complete",
        json={
            "action": "assign",
            "specialistId": str(wrong_specialist),
            "contributorIds": [],
            "reason": "A deliberately invalid delivery assignment is being tested.",
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVALID_ACTION"
    assert not harness.workflow.completion_commands or (
        harness.workflow.completion_commands[-1].action.value != "assign"
    )


async def test_quality_review_stage_is_reached(api_harness: ApiHarness) -> None:
    detail_id = await reach_quality_review(api_harness)
    assert detail_id


async def test_eligible_specialists_are_contextual_and_team_scoped(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await reach_delivery_planning(harness)
    await harness.login("admin8")
    work = await current_item(harness)
    response = await harness.client.get(
        f"/api/v1/work-items/{work['id']}/eligible-specialists"
    )
    assert response.status_code == 200
    assert [item["displayName"] for item in response.json()["items"]] == [
        "Ben Doak",
        "Che Adams",
        "Derek McInnes",
        "Lewis Ferguson",
        "Nathan Patterson",
        "Steve Clarke",
        "Tommy Conway",
    ]

    await harness.login("admin9")
    hidden = await harness.client.get(
        f"/api/v1/work-items/{work['id']}/eligible-specialists"
    )
    assert hidden.status_code == 404

    specialist_id = await harness.user_id("admin11")
    await harness.login("admin8")
    completed = await harness.client.post(
        f"/api/v1/work-items/{work['id']}/complete",
        json={
            "action": "assign",
            "specialistId": str(specialist_id),
            "contributorIds": [],
            "reason": "The Manager selected the accountable delivery Lead.",
        },
        headers=harness.mutation_headers(),
    )
    assert completed.status_code == 200
    stale = await harness.client.get(
        f"/api/v1/work-items/{work['id']}/eligible-specialists"
    )
    assert stale.status_code == 404
