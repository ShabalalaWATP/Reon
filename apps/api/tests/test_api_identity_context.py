"""Secure Customer and staff context switching behaviour."""

from sqlalchemy import select

from conftest import ORIGIN, ApiHarness, request_payload
from istari_service.compliance_models import SecurityEvent
from istari_service.models import Session


async def test_staff_switches_to_customer_and_back_with_rotated_secrets(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    logged_in = await harness.login("admin13")
    assert logged_in["activeContext"] == "STAFF"
    assert logged_in["availableContexts"] == ["STAFF", "CUSTOMER"]
    assert logged_in["user"]["role"] == "DELIVERY_SPECIALIST"
    staff_csrf = harness.csrf_token
    staff_cookie = harness.client.cookies[harness.settings.session_cookie_name]

    switched = await harness.client.post(
        "/api/v1/auth/switch-context",
        json={"context": "CUSTOMER"},
        headers=harness.mutation_headers(),
    )
    assert switched.status_code == 200, switched.text
    customer = switched.json()
    harness.csrf_token = customer["csrfToken"]
    assert customer["activeContext"] == "CUSTOMER"
    assert customer["contextVersion"] == 2
    assert customer["user"]["role"] == "REQUESTER"
    assert customer["user"]["scope"] == "Customer"
    assert customer["user"]["organisationUnitIds"] == []
    assert harness.csrf_token != staff_csrf
    assert harness.client.cookies[harness.settings.session_cookie_name] != staff_cookie

    stale_csrf = await harness.client.post(
        "/api/v1/auth/switch-context",
        json={"context": "STAFF"},
        headers={"Origin": ORIGIN, "X-CSRF-Token": staff_csrf},
    )
    assert stale_csrf.status_code == 403

    created = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(title="Ben's synthetic Customer request"),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    restored = await harness.client.post(
        "/api/v1/auth/switch-context",
        json={"context": "STAFF"},
        headers=harness.mutation_headers(),
    )
    assert restored.status_code == 200, restored.text
    staff = restored.json()
    harness.csrf_token = staff["csrfToken"]
    assert staff["activeContext"] == "STAFF"
    assert staff["contextVersion"] == 3
    assert staff["user"]["role"] == "DELIVERY_SPECIALIST"
    own_staff_read = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert own_staff_read.status_code == 404

    async with harness.sessions() as session:
        stored = await session.scalar(select(Session))
        assert stored is not None
        assert stored.context_version == 3
        events = list(
            await session.scalars(
                select(SecurityEvent).where(
                    SecurityEvent.event_type == "IDENTITY_CONTEXT_SWITCH"
                )
            )
        )
    assert len(events) == 2
    assert all(event.reason_code == "CONTEXT_SWITCHED" for event in events)


async def test_unentitled_customer_and_platform_admin_cannot_change_context(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    customer = await harness.login("admin2")
    assert customer["activeContext"] == "CUSTOMER"
    assert customer["availableContexts"] == ["CUSTOMER"]
    denied_customer = await harness.client.post(
        "/api/v1/auth/switch-context",
        json={"context": "STAFF"},
        headers=harness.mutation_headers(),
    )
    assert denied_customer.status_code == 403

    admin = await harness.login("admin1")
    assert admin["availableContexts"] == ["STAFF"]
    denied_admin = await harness.client.post(
        "/api/v1/auth/switch-context",
        json={"context": "CUSTOMER"},
        headers=harness.mutation_headers(),
    )
    assert denied_admin.status_code == 403
    async with harness.sessions() as session:
        denied_events = list(
            await session.scalars(
                select(SecurityEvent).where(
                    SecurityEvent.event_type == "IDENTITY_CONTEXT_SWITCH",
                    SecurityEvent.reason_code == "CONTEXT_NOT_ENTITLED",
                )
            )
        )
    assert len(denied_events) == 2
