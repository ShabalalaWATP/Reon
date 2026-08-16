from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from conftest import ApiHarness, request_payload
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.schemas.requests import RequestCreate


def _event(
    *,
    title: str = "Protected planning time",
    start: datetime = datetime(2026, 3, 22, 9, tzinfo=UTC),
    recurrence: str = "NONE",
    until: datetime | None = None,
    visibility: str = "PRIVATE",
) -> dict:
    return {
        "title": title,
        "notes": "Synthetic calendar detail used only for local verification.",
        "startsAt": start.isoformat(),
        "endsAt": (start + timedelta(hours=2)).isoformat(),
        "timeZone": "Europe/London",
        "allDay": False,
        "category": "TRAINING",
        "visibility": visibility,
        "recurrence": recurrence,
        "recurrenceInterval": 1,
        "recurrenceUntil": until.isoformat() if until else None,
    }


async def _workspace(harness: ApiHarness, username: str, code: str) -> dict:
    await harness.login(username)
    team_id = str(await harness.unit_id(code))
    response = await harness.client.get("/api/v1/team-workspaces")
    return next(item for item in response.json()["items"] if item["teamId"] == team_id)


async def _personal(harness: ApiHarness, start: str, end: str) -> list[dict]:
    response = await harness.client.get(
        "/api/v1/calendar/personal", params={"from": start, "to": end}
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_personal_recurrence_preserves_wall_time_and_team_privacy(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    ssg = await _workspace(harness, "admin11", "SSG_TEAM")
    created = await harness.client.post(
        "/api/v1/calendar/events",
        json=_event(
            recurrence="WEEKLY",
            until=datetime(2026, 4, 5, 9, tzinfo=UTC),
        ),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 200, created.text
    personal = await _personal(harness, "2026-03-21T00:00:00Z", "2026-04-06T00:00:00Z")
    assert [item["startsAt"] for item in personal] == [
        "2026-03-22T09:00:00Z",
        "2026-03-29T08:00:00Z",
        "2026-04-05T08:00:00Z",
    ]
    assert all(item["title"] == "Protected planning time" for item in personal)

    await harness.login("admin8")
    shared = await harness.client.get(
        f"/api/v1/team-workspaces/{ssg['teamId']}/calendar",
        params={"from": "2026-03-21T00:00:00Z", "to": "2026-04-06T00:00:00Z"},
    )
    assert shared.status_code == 200
    assert {item["title"] for item in shared.json()["items"]} == {"Busy"}
    assert all(item["notes"] is None for item in shared.json()["items"])

    await harness.login("admin24")
    denied = await harness.client.get(
        f"/api/v1/team-workspaces/{ssg['teamId']}/calendar",
        params={"from": "2026-03-21T00:00:00Z", "to": "2026-04-06T00:00:00Z"},
    )
    assert denied.status_code == 404


async def test_manager_team_events_and_subject_commitment_decisions(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    ssg = await _workspace(harness, "admin8", "SSG_TEAM")
    lewis_id = str(await harness.user_id("admin11"))
    requester_id = await harness.user_id("admin2")
    ssg_unit_id = await harness.unit_id("SSG_TEAM")
    async with harness.sessions() as session, session.begin():
        request = ServiceRequest(
            reference="SR-CALENDAR-001",
            requester_id=requester_id,
            status=RequestStatus.IN_PROGRESS,
            current_owner="OSG Team",
            assigned_delivery_team="OSG Team",
            assigned_delivery_team_id=ssg_unit_id,
            **RequestCreate.model_validate(request_payload()).model_dump(),
        )
        session.add(request)
        await session.flush()
        request_id = str(request.id)
    commitment_start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    team_event = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/calendar/events",
        json={
            **_event(
                title="SSG service planning",
                start=commitment_start,
                visibility="TEAM_DETAIL",
            ),
            "grantId": ssg["grantId"],
        },
        headers=harness.mutation_headers(),
    )
    assert team_event.status_code == 200, team_event.text
    commitment = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/calendar/commitments",
        json={
            **_event(
                title="Delivery commitment",
                start=commitment_start,
                visibility="TEAM_DETAIL",
            ),
            "grantId": ssg["grantId"],
            "subjectUserId": lewis_id,
            "requestId": request_id,
        },
        headers=harness.mutation_headers(),
    )
    assert commitment.status_code == 200, commitment.text

    await harness.login("admin11")
    personal = await _personal(harness, "2026-08-31T00:00:00Z", "2026-09-03T00:00:00Z")
    pending = next(item for item in personal if item["title"] == "Delivery commitment")
    assert pending["commitmentStatus"] == "PENDING"
    acknowledged = await harness.client.post(
        f"/api/v1/calendar/events/{pending['eventId']}/acknowledge",
        json={"expectedVersion": pending["version"], "reason": None},
        headers=harness.mutation_headers(),
    )
    assert acknowledged.json()["version"] == 2
    repeated = await harness.client.post(
        f"/api/v1/calendar/events/{pending['eventId']}/dispute",
        json={
            "expectedVersion": 2,
            "reason": "The timing conflicts with another recorded commitment.",
        },
        headers=harness.mutation_headers(),
    )
    assert repeated.status_code == 409

    await harness.login("admin8")
    people = await harness.client.get(f"/api/v1/team-workspaces/{ssg['teamId']}/people")
    lewis = next(
        item
        for item in people.json()["items"]
        if item["displayName"] == "Lewis Ferguson"
    )
    blocked = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/memberships/{lewis['membershipId']}/end",
        json={
            "grantId": ssg["grantId"],
            "expectedVersion": lewis["version"],
            "reason": "Attempting removal while a calendar commitment remains active.",
        },
        headers=harness.mutation_headers(),
    )
    assert blocked.status_code == 409
    assert "calendar commitments" in blocked.json()["detail"]["message"]


async def test_occurrence_edit_cancel_and_future_split_preserve_history(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin11")
    first = datetime(2026, 5, 4, 8, tzinfo=UTC)
    created = await harness.client.post(
        "/api/v1/calendar/events",
        json=_event(
            title="Daily production block",
            start=first,
            recurrence="DAILY",
            until=first + timedelta(days=4),
        ),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 200, created.text
    event_id = created.json()["eventId"]
    second = first + timedelta(days=1)
    edited = await harness.client.post(
        f"/api/v1/calendar/events/{event_id}/occurrences/edit",
        json={
            "expectedVersion": 1,
            "occurrenceStart": second.isoformat(),
            "reason": "The second occurrence needs a later protected period.",
            "title": "Rescheduled production block",
            "notes": "The synthetic occurrence was moved after team planning.",
            "replacementStart": (second + timedelta(hours=2)).isoformat(),
            "replacementEnd": (second + timedelta(hours=4)).isoformat(),
        },
        headers=harness.mutation_headers(),
    )
    assert edited.json()["version"] == 2
    third = first + timedelta(days=2)
    cancelled = await harness.client.post(
        f"/api/v1/calendar/events/{event_id}/occurrences/cancel",
        json={
            "expectedVersion": 2,
            "occurrenceStart": third.isoformat(),
            "reason": "This occurrence is no longer required for delivery.",
        },
        headers=harness.mutation_headers(),
    )
    assert cancelled.json()["version"] == 3
    fourth = first + timedelta(days=3)
    split = await harness.client.post(
        f"/api/v1/calendar/events/{event_id}/split",
        json={
            **_event(
                title="Future production block",
                start=fourth,
                recurrence="DAILY",
                until=fourth + timedelta(days=2),
            ),
            "expectedVersion": 3,
            "splitFrom": fourth.isoformat(),
            "reason": "Future occurrences require a distinct planning pattern.",
        },
        headers=harness.mutation_headers(),
    )
    assert split.status_code == 200, split.text
    items = await _personal(harness, "2026-05-04T00:00:00Z", "2026-05-10T00:00:00Z")
    assert "Rescheduled production block" in {item["title"] for item in items}
    assert not any(
        item["occurrenceStart"] == third.isoformat().replace("+00:00", "Z")
        for item in items
    )
    assert "Future production block" in {item["title"] for item in items}


async def test_capacity_preview_commit_and_stale_snapshot(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    ssg = await _workspace(harness, "admin8", "SSG_TEAM")
    payload = {
        "grantId": ssg["grantId"],
        "dateFrom": date(2026, 6, 1).isoformat(),
        "dateTo": date(2026, 6, 5).isoformat(),
        "timeZone": "Europe/London",
    }
    preview = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/previews",
        json=payload,
        headers=harness.mutation_headers(),
    )
    assert preview.status_code == 200, preview.text
    assert len(preview.json()["days"]) == 5
    committed = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/commits",
        json={"grantId": ssg["grantId"], "token": preview.json()["token"]},
        headers=harness.mutation_headers(),
    )
    assert committed.status_code == 200, committed.text
    repeated = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/commits",
        json={"grantId": ssg["grantId"], "token": preview.json()["token"]},
        headers=harness.mutation_headers(),
    )
    assert repeated.status_code == 409

    stale_preview = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/previews",
        json=payload,
        headers=harness.mutation_headers(),
    )
    await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/calendar/events",
        json={
            **_event(
                title="Capacity changing duty",
                start=datetime(2026, 6, 2, 8, tzinfo=UTC),
                visibility="TEAM_DETAIL",
            ),
            "grantId": ssg["grantId"],
        },
        headers=harness.mutation_headers(),
    )
    stale = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/commits",
        json={"grantId": ssg["grantId"], "token": stale_preview.json()["token"]},
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409

    await harness.login("admin11")
    denied = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/previews",
        json=payload,
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 404


async def test_calendar_validation_update_and_whole_event_cancel(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin11")
    invalid = await harness.client.post(
        "/api/v1/calendar/events",
        json={**_event(), "timeZone": "Not/AZone"},
        headers=harness.mutation_headers(),
    )
    assert invalid.status_code == 409
    created = await harness.client.post(
        "/api/v1/calendar/events",
        json=_event(title="Initial personal event"),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 200, created.text
    event_id = created.json()["eventId"]
    updated = await harness.client.put(
        f"/api/v1/calendar/events/{event_id}",
        json={**_event(title="Updated personal event"), "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert updated.json()["version"] == 2
    cancelled = await harness.client.post(
        f"/api/v1/calendar/events/{event_id}/cancel",
        json={
            "expectedVersion": 2,
            "occurrenceStart": "2026-03-22T09:00:00Z",
            "reason": "The complete personal event is no longer required.",
        },
        headers=harness.mutation_headers(),
    )
    assert cancelled.json()["version"] == 3
    too_wide = await harness.client.get(
        "/api/v1/calendar/personal",
        params={"from": "2025-01-01T00:00:00Z", "to": "2027-01-01T00:00:00Z"},
    )
    assert too_wide.status_code == 409
