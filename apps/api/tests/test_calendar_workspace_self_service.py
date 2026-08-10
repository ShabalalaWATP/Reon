"""Calendar self-service across routing and delivery workspaces."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from conftest import ApiHarness


def _event() -> dict:
    starts = datetime.now(UTC) + timedelta(days=2)
    return {
        "title": "Synthetic training course",
        "notes": "Personal learning activity recorded by the workspace Member.",
        "startsAt": starts.isoformat(),
        "endsAt": (starts + timedelta(hours=3)).isoformat(),
        "timeZone": "Europe/London",
        "allDay": False,
        "category": "TRAINING",
        "visibility": "AVAILABILITY_ONLY",
        "recurrence": "NONE",
        "recurrenceInterval": 1,
        "recurrenceUntil": None,
    }


async def test_routing_member_can_create_personal_activity_but_not_unit_event(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin75")
    created = await harness.client.post(
        "/api/v1/calendar/events",
        json=_event(),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 200, created.text
    assert created.json()["eventId"]
    jioc_id = await harness.unit_id("JIOC")
    workspaces = await harness.client.get("/api/v1/team-workspaces")
    jioc = next(
        item for item in workspaces.json()["items"] if item["teamId"] == str(jioc_id)
    )
    assert jioc["workspacePosition"] == "MEMBER"
    assert jioc["grantId"] is None
    denied = await harness.client.post(
        f"/api/v1/team-workspaces/{jioc_id}/calendar/events",
        json={**_event(), "grantId": str(uuid4())},
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 404


async def test_non_member_cannot_create_a_personal_workspace_event(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    denied = await harness.client.post(
        "/api/v1/calendar/events",
        json=_event(),
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 404
