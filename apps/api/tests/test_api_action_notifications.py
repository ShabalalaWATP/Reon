"""End-to-end personal workspace projection from ordinary workflow actions."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI

from api_helpers import perform
from conftest import ApiHarness, request_payload
from mist_service.routers.actions import router as personal_router


def _install_personal_routes(harness: ApiHarness) -> None:
    transport = harness.client._transport  # type: ignore[attr-defined]
    app = transport.app  # type: ignore[attr-defined]
    assert isinstance(app, FastAPI)
    if not any(
        getattr(route, "path", None) == "/api/v1/me/actions" for route in app.routes
    ):
        app.include_router(personal_router, prefix="/api/v1")


async def test_existing_workflow_events_drive_actions_and_notifications(
    api_harness: ApiHarness,
) -> None:
    _install_personal_routes(api_harness)
    await api_harness.login("admin2")
    submitted = await api_harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=api_harness.mutation_headers(),
    )
    assert submitted.status_code == 201

    await api_harness.login("admin4")
    intake_actions = await api_harness.client.get("/api/v1/me/actions")
    assert intake_actions.status_code == 200
    intake_body = intake_actions.json()
    assert intake_body["items"][0]["actionType"] == "REVIEW_SUBMISSION"
    assert intake_body["items"][0]["reference"] == submitted.json()["reference"]
    assert intake_body["items"][0]["actionAccess"] == "SHARED"
    assert intake_body["items"][0]["deepLink"] == (
        f"/triage?requestId={submitted.json()['id']}"
    )
    assert intake_body["freshness"]["status"] == "CURRENT"

    intake_notifications = await api_harness.client.get("/api/v1/me/notifications")
    assert intake_notifications.status_code == 200
    assert any(
        item["eventType"] == "REQUEST_SUBMITTED"
        for item in intake_notifications.json()["items"]
    )

    assert await api_harness.dispatch_start()
    filtered = await api_harness.client.get(
        "/api/v1/work-items", params={"requestId": submitted.json()["id"]}
    )
    assert filtered.status_code == 200
    assert [item["requestId"] for item in filtered.json()["items"]] == [
        submitted.json()["id"]
    ]
    hidden = await api_harness.client.get(
        "/api/v1/work-items", params={"requestId": str(uuid4())}
    )
    assert hidden.status_code == 200
    assert hidden.json()["items"] == []
    intake_item = filtered.json()["items"][0]
    claimed = await api_harness.client.post(
        f"/api/v1/work-items/{intake_item['id']}/claim",
        headers=api_harness.mutation_headers(),
    )
    assert claimed.status_code == 200
    personal = (await api_harness.client.get("/api/v1/me/actions")).json()["items"]
    assert personal[0]["actionAccess"] == "PERSONAL"

    await api_harness.login("admin7")
    assert (await api_harness.client.get("/api/v1/me/actions")).json()["items"] == []

    await perform(
        api_harness,
        "admin4",
        {"action": "progress", "priority": "MEDIUM"},
    )
    await api_harness.login("admin5")
    command_actions = await api_harness.client.get("/api/v1/me/actions")
    assert command_actions.status_code == 200
    assert command_actions.json()["items"][0]["actionType"] == "CHOOSE_OPS_GROUP"
    assert command_actions.json()["items"][0]["currentOwner"] == (
        "DIGOC · Awaiting owner"
    )
    assert command_actions.json()["items"][0]["deepLink"] == (
        f"/coordination?requestId={submitted.json()['id']}"
    )

    command_notifications = await api_harness.client.get(
        "/api/v1/me/notifications?eventTypes=TASK_ASSIGNED"
    )
    assert command_notifications.status_code == 200
    assert len(command_notifications.json()["items"]) == 1
    assert command_notifications.json()["unreadCount"] == 1

    await api_harness.login("admin21")
    hidden = await api_harness.client.get("/api/v1/me/actions")
    assert hidden.status_code == 200
    assert hidden.json()["items"] == []
