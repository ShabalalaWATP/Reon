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
        "visibility": "TEAM_DETAIL",
        "recurrence": "NONE",
        "recurrenceInterval": 1,
        "recurrenceUntil": None,
    }


async def test_routing_member_can_create_personal_activity_but_not_unit_event(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin75")
    event = _event()
    created = await harness.client.post(
        "/api/v1/calendar/events",
        json=event,
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 200, created.text
    assert created.json()["eventId"]
    crioc_id = await harness.unit_id("CRIOC")
    workspaces = await harness.client.get("/api/v1/team-workspaces")
    crioc = next(
        item for item in workspaces.json()["items"] if item["teamId"] == str(crioc_id)
    )
    assert crioc["workspacePosition"] == "MEMBER"
    assert crioc["grantId"] is None
    denied = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc_id}/calendar/events",
        json={**_event(), "grantId": str(uuid4())},
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 404

    await harness.login("admin4")
    shared = await harness.client.get(
        f"/api/v1/team-workspaces/{crioc_id}/calendar",
        params={
            "from": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "to": (datetime.now(UTC) + timedelta(days=4)).isoformat(),
        },
    )
    assert shared.status_code == 200
    projected = next(
        item
        for item in shared.json()["items"]
        if item["eventId"] == created.json()["eventId"]
    )
    assert projected["title"] == event["title"]
    assert projected["notes"] == event["notes"]


async def test_account_without_a_workspace_can_use_a_personal_calendar(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    created = await harness.client.post(
        "/api/v1/calendar/events",
        json=_event(),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 200, created.text
    now = datetime.now(UTC)
    personal = await harness.client.get(
        "/api/v1/calendar/personal",
        params={
            "from": (now + timedelta(days=1)).isoformat(),
            "to": (now + timedelta(days=4)).isoformat(),
        },
    )
    assert personal.status_code == 200
    assert any(
        item["eventId"] == created.json()["eventId"]
        for item in personal.json()["items"]
    )


async def test_personal_activity_requires_team_detail_or_explicit_private_visibility(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin75")
    ambiguous = await harness.client.post(
        "/api/v1/calendar/events",
        json={**_event(), "visibility": "AVAILABILITY_ONLY"},
        headers=harness.mutation_headers(),
    )
    assert ambiguous.status_code == 409
    assert "Private appointment" in ambiguous.json()["detail"]["message"]

    private = await harness.client.post(
        "/api/v1/calendar/events",
        json={**_event(), "visibility": "PRIVATE"},
        headers=harness.mutation_headers(),
    )
    assert private.status_code == 200
