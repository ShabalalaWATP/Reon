"""Regression coverage for effective Customer context isolation."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from conftest import ApiHarness, request_payload
from mist_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEventGroup,
)
from mist_service.domain import Actor
from mist_service.models import UserRole
from mist_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from mist_service.repositories.notifications import SqlAlchemyNotificationRepository
from mist_service.services.notification_service import (
    NotificationEventCommand,
    NotificationService,
)


async def _switch_context(harness: ApiHarness, context: str) -> dict:
    response = await harness.client.post(
        "/api/v1/auth/switch-context",
        json={"context": context},
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    harness.csrf_token = response.json()["csrfToken"]
    return response.json()


@pytest.mark.parametrize("username", ["admin8", "admin13"])
async def test_customer_context_cannot_reuse_staff_workspace_authority(
    api_harness: ApiHarness, username: str
) -> None:
    harness = api_harness
    await harness.login(username)
    team_id = await harness.unit_id("SSG_TEAM")
    staff_workspace = await harness.client.get("/api/v1/team-workspaces")
    assert staff_workspace.status_code == 200
    access = next(
        item
        for item in staff_workspace.json()["items"]
        if item["teamId"] == str(team_id)
    )
    await _switch_context(harness, "CUSTOMER")

    now = datetime.now(UTC)
    reads = [
        "/api/v1/team-workspaces",
        f"/api/v1/team-workspaces/{team_id}",
        f"/api/v1/team-workspaces/{team_id}/people",
        f"/api/v1/team-workspaces/{team_id}/activity",
        f"/api/v1/team-workspaces/{team_id}/board",
        f"/api/v1/team-workspaces/{team_id}/planning/cockpit",
        "/api/v1/me/actions",
    ]
    for path in reads:
        response = await harness.client.get(path)
        assert response.status_code == 404, (path, response.text)

    calendar = await harness.client.get(
        f"/api/v1/team-workspaces/{team_id}/calendar",
        params={
            "from": now.isoformat(),
            "to": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert calendar.status_code == 404

    statistics = await harness.client.get("/api/v1/statistics/scopes")
    assert statistics.status_code == 200
    assert statistics.json() == {"items": []}

    roster = await harness.client.post(
        f"/api/v1/team-workspaces/{team_id}/memberships",
        json={
            "grantId": access.get("grantId") or "00000000-0000-0000-0000-000000000000",
            "analystId": str(await harness.user_id("admin13")),
            "reason": "A synthetic attempt from the wrong effective context.",
        },
        headers=harness.mutation_headers(),
    )
    assert roster.status_code == 404

    created = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(title=f"Synthetic own request for {username}"),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    own = await harness.client.get(f"/api/v1/requests/{created.json()['id']}")
    assert own.status_code == 200


async def test_dual_context_notification_preferences_are_independent(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    staff = await harness.login("admin13")
    customer = await _switch_context(harness, "CUSTOMER")
    for group in ("REVIEW", "ASSIGNMENT", "CLARIFICATION"):
        updated = await harness.client.patch(
            f"/api/v1/me/notifications/preferences/{group}",
            json={"enabled": False, "reminderDays": [], "expectedVersion": 0},
            headers=harness.mutation_headers(),
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["enabled"] is False

    await _switch_context(harness, "STAFF")
    staff_preferences = await harness.client.get("/api/v1/me/notifications/preferences")
    assert staff_preferences.status_code == 200
    staff_groups = {
        item["eventGroup"]: item for item in staff_preferences.json()["groups"]
    }
    assert staff_groups["REVIEW"]["enabled"] is True
    assert staff_groups["ASSIGNMENT"]["enabled"] is True
    assert staff_groups["CLARIFICATION"]["enabled"] is True
    assert staff_groups["REVIEW"]["version"] == 0

    staff_actor = _actor(staff)
    customer_actor = _actor(customer)
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        service = NotificationService(
            SqlAlchemyNotificationRepository(session),
            SqlAlchemyNotificationProjectionRepository(session),
        )
        staff_event = await service.publish(
            NotificationEventCommand(
                stable_key="context:staff-assignment",
                event_type="TASK_ASSIGNED",
                event_group=NotificationEventGroup.ASSIGNMENT,
                source_version=1,
                reference="SR-SYNTHETIC-STAFF",
                occurred_at=now,
            )
        )
        staff_created = await service.project(
            staff_event.id,
            [
                RecipientRule(
                    staff_actor.id,
                    NotificationAccessKind.ACCOUNT,
                    staff_actor.role,
                )
            ],
            projected_at=now,
        )
        assert len(staff_created) == 1
        customer_event = await service.publish(
            NotificationEventCommand(
                stable_key="context:customer-assignment",
                event_type="TASK_ASSIGNED",
                event_group=NotificationEventGroup.ASSIGNMENT,
                source_version=1,
                reference="SR-SYNTHETIC-CUSTOMER",
                occurred_at=now,
            )
        )
        assert (
            await service.project(
                customer_event.id,
                [
                    RecipientRule(
                        customer_actor.id,
                        NotificationAccessKind.ACCOUNT,
                        UserRole.REQUESTER,
                    )
                ],
                projected_at=now,
            )
            == []
        )


def _actor(session: dict) -> Actor:
    user = session["user"]
    return Actor(
        id=UUID(user["id"]),
        username=user["username"],
        display_name=user["displayName"],
        role=UserRole(user["role"]),
        scope=user["scope"],
        organisation_unit_ids=frozenset(
            UUID(item) for item in user["organisationUnitIds"]
        ),
    )
