"""Platform classification and non-enumerating access-assistance behaviour."""

from __future__ import annotations

from sqlalchemy import func, select

from conftest import ApiHarness
from istari_service.action_notification_models import (
    NotificationEvent,
    NotificationRecipient,
)
from istari_service.admin_models import AdminAuditEvent
from istari_service.models import User, UserRole
from istari_service.platform_security_models import (
    PasswordAssistanceAttempt,
    PlatformClassificationSetting,
)


def test_platform_classification_persists_public_values() -> None:
    classification_type = PlatformClassificationSetting.__table__.c.classification.type
    assert classification_type.enums == [
        "OFFICIAL",
        "OFFICIAL-SENSITIVE",
        "SECRET",
        "TOP-SECRET",
    ]


async def test_global_classification_requires_elevated_administrator(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    initial = await harness.client.get("/api/v1/platform/classification")
    assert initial.status_code == 200
    assert initial.json()["classification"] == "OFFICIAL"
    assert initial.json()["version"] == 1

    await harness.login("admin2")
    denied = await harness.client.patch(
        "/api/v1/admin/platform/classification",
        json={"classification": "SECRET", "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 403

    await harness.login("admin1")
    step_up = await harness.client.patch(
        "/api/v1/admin/platform/classification",
        json={"classification": "SECRET", "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert step_up.status_code == 403
    assert step_up.json()["detail"]["code"] == "STEP_UP_REQUIRED"

    await harness.elevate()
    changed = await harness.client.patch(
        "/api/v1/admin/platform/classification",
        json={"classification": "SECRET", "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["classification"] == "SECRET"
    assert changed.json()["version"] == 2
    assert (
        await harness.client.get("/api/v1/platform/classification")
    ).json() == changed.json()

    stale = await harness.client.patch(
        "/api/v1/admin/platform/classification",
        json={"classification": "TOP-SECRET", "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "STALE_VERSION"
    async with harness.sessions() as session:
        audit = await session.scalar(
            select(AdminAuditEvent).where(
                AdminAuditEvent.action == "CLASSIFICATION_UPDATED"
            )
        )
        assert audit is not None
        assert audit.changed_fields == ["classification"]


async def test_password_assistance_is_neutral_bounded_and_admin_only(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    expected = {
        "status": "accepted",
        "message": (
            "If an active account matches that email, "
            "an administrator has been notified."
        ),
    }
    responses = [
        await harness.client.post(
            "/api/v1/auth/password-assistance",
            json={"email": email},
        )
        for email in (
            "ADMIN2@ISTARI.EXAMPLE.TEST",
            "admin2@istari.example.test",
            "admin16@istari.example.test",
            "unknown@istari.example.test",
        )
    ]
    assert all(response.status_code == 202 for response in responses)
    assert all(response.json() == expected for response in responses)
    invalid = await harness.client.post(
        "/api/v1/auth/password-assistance",
        json={"email": "not-an-email"},
    )
    assert invalid.status_code == 422

    async with harness.sessions() as session:
        assert (
            await session.scalar(select(func.count(PasswordAssistanceAttempt.id))) == 4
        )
        event_count = await session.scalar(
            select(func.count(NotificationEvent.id)).where(
                NotificationEvent.event_type == "PASSWORD_ASSISTANCE_REQUESTED"
            )
        )
        assert event_count == 1
        attempt_columns = set(PasswordAssistanceAttempt.__table__.columns.keys())
        assert "email" not in attempt_columns

    await harness.login("admin1")
    notifications = await harness.client.get("/api/v1/me/notifications")
    assert notifications.status_code == 200
    assistance = [
        item
        for item in notifications.json()["items"]
        if item["eventType"] == "PASSWORD_ASSISTANCE_REQUESTED"
    ]
    assert len(assistance) == 1
    assert assistance[0]["subject"] == "admin2: password assistance requested."
    assert assistance[0]["deepLink"].startswith("/admin/users/")

    async with harness.sessions() as session:
        administrator_count = await session.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.PLATFORM_ADMIN,
                User.is_active.is_(True),
            )
        )
        recipient_count = await session.scalar(
            select(func.count(NotificationRecipient.id))
            .join(
                NotificationEvent,
                NotificationEvent.id == NotificationRecipient.notification_event_id,
            )
            .where(NotificationEvent.event_type == "PASSWORD_ASSISTANCE_REQUESTED")
        )
        assert recipient_count == administrator_count

    await harness.login("admin2")
    requester_notifications = await harness.client.get("/api/v1/me/notifications")
    assert all(
        item["eventType"] != "PASSWORD_ASSISTANCE_REQUESTED"
        for item in requester_notifications.json()["items"]
    )


async def test_password_assistance_source_budget_keeps_the_public_result_neutral(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    results = [
        await harness.client.post(
            "/api/v1/auth/password-assistance",
            json={"email": f"unknown-{index}@istari.example.test"},
        )
        for index in range(6)
    ]
    assert all(result.status_code == 202 for result in results)
    assert len({result.text for result in results}) == 1
    async with harness.sessions() as session:
        assert (
            await session.scalar(select(func.count(PasswordAssistanceAttempt.id))) == 5
        )
