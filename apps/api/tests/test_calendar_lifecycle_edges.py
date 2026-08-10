"""Security and lifecycle edges for the canonical calendar API."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from conftest import ApiHarness, request_payload
from istari_service.calendar_models import CalendarCapacityPreview
from istari_service.models import RequestStatus, ServiceRequest
from istari_service.schemas.requests import RequestCreate


def event_payload(
    *,
    start: datetime = datetime(2026, 8, 10, 9, tzinfo=UTC),
    recurrence: str = "NONE",
    until: datetime | None = None,
    **updates: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Synthetic calendar activity",
        "notes": "Required synthetic calendar detail for boundary testing.",
        "startsAt": start.isoformat(),
        "endsAt": (start + timedelta(hours=2)).isoformat(),
        "timeZone": "Europe/London",
        "allDay": False,
        "category": "SERVICE_WORK",
        "visibility": "PRIVATE",
        "recurrence": recurrence,
        "recurrenceInterval": 1,
        "recurrenceUntil": until.isoformat() if until else None,
    }
    payload.update(updates)
    return payload


async def workspace(harness: ApiHarness, username: str = "admin8") -> dict:
    await harness.login(username)
    team_id = str(await harness.unit_id("SSG_TEAM"))
    response = await harness.client.get("/api/v1/team-workspaces")
    return next(item for item in response.json()["items"] if item["teamId"] == team_id)


async def test_personal_calendar_preserves_ownership_and_lifecycle_failures(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin1")
    administrator_event = await harness.client.post(
        "/api/v1/calendar/events",
        json=event_payload(),
        headers=harness.mutation_headers(),
    )
    assert administrator_event.status_code == 200

    await harness.login("admin11")
    too_long = await harness.client.post(
        "/api/v1/calendar/events",
        json=event_payload(
            recurrence="DAILY",
            until=datetime(2027, 9, 1, 9, tzinfo=UTC),
        ),
        headers=harness.mutation_headers(),
    )
    assert too_long.status_code == 409
    created = await harness.client.post(
        "/api/v1/calendar/events",
        json=event_payload(),
        headers=harness.mutation_headers(),
    )
    event_id = created.json()["eventId"]

    await harness.login("admin12")
    hidden = await harness.client.put(
        f"/api/v1/calendar/events/{event_id}",
        json={**event_payload(title="Impermissible change"), "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert hidden.status_code == 404

    await harness.login("admin11")
    stale = await harness.client.put(
        f"/api/v1/calendar/events/{event_id}",
        json={**event_payload(), "expectedVersion": 2},
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409
    missing = await harness.client.put(
        f"/api/v1/calendar/events/{uuid4()}",
        json={**event_payload(), "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert missing.status_code == 404
    cancelled = await harness.client.post(
        f"/api/v1/calendar/events/{event_id}/cancel",
        json={
            "expectedVersion": 1,
            "occurrenceStart": "2026-08-10T09:00:00Z",
            "reason": "Required complete cancellation reason.",
        },
        headers=harness.mutation_headers(),
    )
    assert cancelled.status_code == 200
    cannot_change_cancelled = await harness.client.put(
        f"/api/v1/calendar/events/{event_id}",
        json={**event_payload(), "expectedVersion": 2},
        headers=harness.mutation_headers(),
    )
    assert cannot_change_cancelled.status_code == 409


async def test_team_calendar_enforces_exact_manager_and_subject_authority(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    ssg = await workspace(harness)
    team_event = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/calendar/events",
        json={
            **event_payload(visibility="TEAM_DETAIL"),
            "grantId": ssg["grantId"],
        },
        headers=harness.mutation_headers(),
    )
    assert team_event.status_code == 200

    await harness.login("admin11")
    denied_change = await harness.client.put(
        f"/api/v1/calendar/events/{team_event.json()['eventId']}",
        json={**event_payload(), "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert denied_change.status_code == 404

    ssg = await workspace(harness)
    requester_id = await harness.user_id("admin2")
    ssg_unit_id = await harness.unit_id("SSG_TEAM")
    async with harness.sessions() as session, session.begin():
        request = ServiceRequest(
            reference="SR-CALENDAR-AUTHORITY",
            requester_id=requester_id,
            status=RequestStatus.IN_PROGRESS,
            current_owner="SSG Team",
            assigned_delivery_team="SSG Team",
            assigned_delivery_team_id=ssg_unit_id,
            **RequestCreate.model_validate(request_payload()).model_dump(),
        )
        session.add(request)
        await session.flush()
        request_id = str(request.id)
    non_member = await harness.user_id("admin1")
    invalid_subject = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/calendar/commitments",
        json={
            **event_payload(visibility="TEAM_DETAIL"),
            "grantId": ssg["grantId"],
            "requestId": request_id,
            "subjectUserId": str(non_member),
        },
        headers=harness.mutation_headers(),
    )
    assert invalid_subject.status_code == 404
    analyst_id = await harness.user_id("admin11")
    commitment = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/calendar/commitments",
        json={
            **event_payload(visibility="TEAM_DETAIL"),
            "grantId": ssg["grantId"],
            "requestId": request_id,
            "subjectUserId": str(analyst_id),
        },
        headers=harness.mutation_headers(),
    )
    assert commitment.status_code == 200

    await harness.login("admin12")
    wrong_subject = await harness.client.post(
        f"/api/v1/calendar/events/{commitment.json()['eventId']}/dispute",
        json={
            "expectedVersion": 1,
            "reason": "Another Analyst cannot dispute this commitment.",
        },
        headers=harness.mutation_headers(),
    )
    assert wrong_subject.status_code == 404
    await harness.login("admin11")
    no_reason = await harness.client.post(
        f"/api/v1/calendar/events/{commitment.json()['eventId']}/dispute",
        json={"expectedVersion": 1, "reason": None},
        headers=harness.mutation_headers(),
    )
    assert no_reason.status_code == 409


async def test_occurrence_and_split_reject_invalid_or_duplicate_changes(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin11")
    first = datetime(2026, 8, 10, 9, tzinfo=UTC)
    recurring = await harness.client.post(
        "/api/v1/calendar/events",
        json=event_payload(
            start=first,
            recurrence="DAILY",
            until=first + timedelta(days=4),
        ),
        headers=harness.mutation_headers(),
    )
    event_id = recurring.json()["eventId"]
    invalid_occurrence = await harness.client.post(
        f"/api/v1/calendar/events/{event_id}/occurrences/cancel",
        json={
            "expectedVersion": 1,
            "occurrenceStart": (first + timedelta(hours=3)).isoformat(),
            "reason": "This is not a valid recurrence boundary.",
        },
        headers=harness.mutation_headers(),
    )
    assert invalid_occurrence.status_code == 409
    cancelled = await harness.client.post(
        f"/api/v1/calendar/events/{event_id}/occurrences/cancel",
        json={
            "expectedVersion": 1,
            "occurrenceStart": first.isoformat(),
            "reason": "Required first occurrence cancellation reason.",
        },
        headers=harness.mutation_headers(),
    )
    assert cancelled.status_code == 200
    duplicate = await harness.client.post(
        f"/api/v1/calendar/events/{event_id}/occurrences/cancel",
        json={
            "expectedVersion": 2,
            "occurrenceStart": first.isoformat(),
            "reason": "Required duplicate cancellation reason.",
        },
        headers=harness.mutation_headers(),
    )
    assert duplicate.status_code == 409
    split_point = first + timedelta(days=1)
    early_replacement = await harness.client.post(
        f"/api/v1/calendar/events/{event_id}/split",
        json={
            **event_payload(
                start=first,
                recurrence="DAILY",
                until=first + timedelta(days=3),
            ),
            "expectedVersion": 2,
            "splitFrom": split_point.isoformat(),
            "reason": "Replacement cannot start before the split point.",
        },
        headers=harness.mutation_headers(),
    )
    assert early_replacement.status_code == 409

    single = await harness.client.post(
        "/api/v1/calendar/events",
        json=event_payload(start=first + timedelta(days=10)),
        headers=harness.mutation_headers(),
    )
    non_recurring_split = await harness.client.post(
        f"/api/v1/calendar/events/{single.json()['eventId']}/split",
        json={
            **event_payload(
                start=first + timedelta(days=10),
                recurrence="DAILY",
                until=first + timedelta(days=12),
            ),
            "expectedVersion": 1,
            "splitFrom": (first + timedelta(days=10)).isoformat(),
            "reason": "A non-recurring event cannot be split.",
        },
        headers=harness.mutation_headers(),
    )
    assert non_recurring_split.status_code == 409


async def test_capacity_rejects_bad_ranges_tokens_and_expired_previews(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    ssg = await workspace(harness)
    base = {
        "grantId": ssg["grantId"],
        "dateFrom": date(2026, 9, 4).isoformat(),
        "dateTo": date(2026, 9, 6).isoformat(),
        "timeZone": "Europe/London",
    }
    bad_zone = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/previews",
        json={**base, "timeZone": "Not/AZone"},
        headers=harness.mutation_headers(),
    )
    assert bad_zone.status_code == 409
    bad_range = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/previews",
        json={**base, "dateTo": date(2027, 1, 1).isoformat()},
        headers=harness.mutation_headers(),
    )
    assert bad_range.status_code == 409
    missing = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/commits",
        json={"grantId": ssg["grantId"], "token": "x" * 32},
        headers=harness.mutation_headers(),
    )
    assert missing.status_code == 409

    preview = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/previews",
        json=base,
        headers=harness.mutation_headers(),
    )
    days = preview.json()["days"]
    assert days[0]["baselineMinutes"] > 0
    assert [day["baselineMinutes"] for day in days[1:]] == [0, 0]
    async with harness.sessions() as session:
        stored = await session.scalar(
            select(CalendarCapacityPreview).where(
                CalendarCapacityPreview.token == preview.json()["token"]
            )
        )
        assert stored is not None
        stored.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()
    expired = await harness.client.post(
        f"/api/v1/team-workspaces/{ssg['teamId']}/capacity/commits",
        json={"grantId": ssg["grantId"], "token": preview.json()["token"]},
        headers=harness.mutation_headers(),
    )
    assert expired.status_code == 409
