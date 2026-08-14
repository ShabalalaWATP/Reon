"""HTTP authentication, CSRF and object-concealment controls."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import select

from api_helpers import current_item, submit_request
from conftest import ORIGIN, ApiHarness, request_payload
from istari_service.models import Session, User


async def test_generic_login_failure_for_unknown_disabled_and_wrong_password(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    bodies = []
    for username, password in (
        ("missing@example.test", "not-the-password"),
        ("admin16", "Synthetic-demo-passphrase-42"),
        ("admin2", "not-the-password"),
    ):
        response = await harness.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert response.status_code == 401
        bodies.append(response.json())
    assert bodies[0] == bodies[1] == bodies[2]
    assert bodies[0]["detail"]["code"] == "AUTHENTICATION_FAILED"


async def test_login_rate_limit_is_account_neutral_and_advertises_retry(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    harness.settings.login_rate_limit_per_source = 2
    harness.settings.login_rate_limit_global = 20
    bodies = []
    for suffix in range(2):
        response = await harness.client.post(
            "/api/v1/auth/login",
            json={
                "username": f"missing-{suffix}@example.test",
                "password": "not-the-password",
            },
        )
        assert response.status_code == 401
        bodies.append(response.json())

    limited = await harness.client.post(
        "/api/v1/auth/login",
        json={"username": "admin2", "password": "not-the-password"},
    )
    assert limited.status_code == 429
    assert limited.json()["detail"] == {
        "code": "AUTHENTICATION_RATE_LIMITED",
        "message": "Sign-in is temporarily unavailable. Try again shortly.",
    }
    assert 1 <= int(limited.headers["Retry-After"]) <= 60
    assert bodies[0] == bodies[1]


async def test_csrf_requires_current_token_and_trusted_origin(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    valid_token = harness.csrf_token
    missing = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
    )
    assert missing.status_code == 403
    wrong_origin = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(origin="https://untrusted.example"),
    )
    assert wrong_origin.status_code == 403

    me = await harness.client.get("/api/v1/auth/me")
    assert me.status_code == 200
    capabilities = await harness.client.get("/api/v1/me/capabilities")
    assert capabilities.json() == {
        "myWork": True,
        "notifications": True,
        "configuration": True,
        "products": True,
        "managedFileUploads": True,
        "planning": True,
        "statistics": True,
        "conversationReads": True,
        "conversationWrites": True,
        "contextSwitching": True,
    }
    harness.csrf_token = me.json()["csrfToken"]
    still_current = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers={"Origin": ORIGIN, "X-CSRF-Token": valid_token},
    )
    assert still_current.status_code == 201
    accepted = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert accepted.status_code == 201


async def test_logout_revokes_cookie_session(api_harness: ApiHarness) -> None:
    harness = api_harness
    await harness.login("admin2")
    logout = await harness.client.post(
        "/api/v1/auth/logout",
        headers=harness.mutation_headers(),
    )
    assert logout.status_code == 204
    assert (await harness.client.get("/api/v1/auth/me")).status_code == 401


async def test_failed_login_state_is_committed_before_error_response(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    for _ in range(5):
        response = await harness.client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin2",
                "password": "not-the-password",
            },
        )
        assert response.status_code == 401

    async with harness.sessions() as session:
        user = await session.scalar(select(User).where(User.username == "admin2"))
        assert user is not None
        assert user.failed_login_count == 0
        assert user.locked_until is not None

    locked = await harness.client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin2",
            "password": "Synthetic-demo-passphrase-42",
        },
    )
    assert locked.status_code == 200


async def test_invalid_session_revocation_survives_expected_401(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    user_id = await harness.user_id("admin2")
    async with harness.sessions() as session, session.begin():
        user = await session.get(User, user_id)
        assert user is not None
        user.is_active = False

    assert (await harness.client.get("/api/v1/auth/me")).status_code == 401
    async with harness.sessions() as session, session.begin():
        stored = await session.scalar(select(Session).where(Session.user_id == user_id))
        user = await session.get(User, user_id)
        assert stored is not None and stored.revoked_at is not None
        assert user is not None
        user.is_active = True

    assert (await harness.client.get("/api/v1/auth/me")).status_code == 401


async def test_request_validation_rejects_privileged_and_invalid_fields(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    privileged = request_payload(assignedDeliveryTeam="DELIVERY_TEAM_A")
    response = await harness.client.post(
        "/api/v1/requests",
        json=privileged,
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 422
    internal_route_field = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(requestingBusinessArea="Requesting Area B"),
        headers=harness.mutation_headers(),
    )
    assert internal_route_field.status_code == 422


async def test_validation_errors_never_echo_password_or_context(
    api_harness: ApiHarness,
) -> None:
    password = "s" * 1_100
    response = await api_harness.client.post(
        "/api/v1/auth/login",
        json={"username": "admin2", "password": password},
    )
    assert response.status_code == 422
    assert password not in response.text
    errors = response.json()["detail"]
    assert errors
    assert all(set(error) == {"loc", "msg", "type"} for error in errors)
    assert all(len(error["msg"]) <= 200 for error in errors)


async def test_declared_and_streamed_oversized_bodies_are_rejected(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    oversized = b"x" * (harness.settings.max_request_body_bytes + 1)
    declared = await harness.client.post(
        "/api/v1/auth/login",
        content=oversized,
        headers={"Content-Type": "application/json"},
    )
    assert declared.status_code == 413
    assert declared.json()["detail"]["code"] == "REQUEST_TOO_LARGE"

    async def streamed_body() -> AsyncIterator[bytes]:
        midpoint = len(oversized) // 2
        yield oversized[:midpoint]
        yield oversized[midpoint:]

    streamed = await harness.client.post(
        "/api/v1/auth/login",
        content=streamed_body(),
        headers={"Content-Type": "application/json"},
    )
    assert streamed.status_code == 413
    assert streamed.json()["detail"]["code"] == "REQUEST_TOO_LARGE"


async def test_platform_support_has_no_request_or_work_access(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await submit_request(harness)
    await harness.login("admin1")
    detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert detail.status_code == 404
    listing = await harness.client.get("/api/v1/requests")
    assert listing.status_code == 404
    work = await harness.client.get("/api/v1/work-items")
    assert work.status_code == 200
    assert work.json() == {"items": [], "nextCursor": None}


async def test_direct_api_host_and_response_headers_are_hardened(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    rejected = await harness.client.get(
        "/health",
        headers={"Host": "untrusted.example.test"},
    )
    assert rejected.status_code == 400

    api_response = await harness.client.get("/api/v1/auth/me")
    assert api_response.status_code == 401
    assert api_response.headers["Cache-Control"] == "no-store"
    assert api_response.headers["X-Content-Type-Options"] == "nosniff"
    assert api_response.headers["X-Frame-Options"] == "DENY"
    assert api_response.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
    assert api_response.headers["Referrer-Policy"] == "no-referrer"
    assert api_response.headers["Permissions-Policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )
    assert api_response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert api_response.headers["Cross-Origin-Embedder-Policy"] == "require-corp"
    assert api_response.headers["Cross-Origin-Resource-Policy"] == "same-origin"

    health = await harness.client.get("/health")
    assert health.headers["Cache-Control"] == "no-store"


async def test_inaccessible_claim_is_concealed(api_harness: ApiHarness) -> None:
    harness = api_harness
    await submit_request(harness)
    await harness.login("admin4")
    item = await current_item(harness)
    await harness.login("admin5")
    response = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/claim",
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 404


async def test_request_detail_is_visible_only_to_the_active_assignee(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await submit_request(harness)
    await harness.login("admin4")
    await current_item(harness)
    owner_detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert owner_detail.status_code == 200

    await harness.login("admin7")
    assert (await harness.client.get("/api/v1/work-items")).json() == {
        "items": [],
        "nextCursor": None,
    }
    colleague_detail = await harness.client.get(f"/api/v1/requests/{request_id}")
    assert colleague_detail.status_code == 404


async def test_unclaimed_completion_and_wrong_action_are_rejected(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await submit_request(harness)
    await harness.login("admin4")
    listing = await harness.client.get("/api/v1/work-items")
    item = listing.json()["items"][0]
    response = await harness.client.post(
        f"/api/v1/work-items/{item['id']}/complete",
        json={"action": "close", "reason": "Human closure reason."},
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 409
    claimed = await current_item(harness)
    invalid = await harness.client.post(
        f"/api/v1/work-items/{claimed['id']}/complete",
        json={"action": "release", "recipients": ["Someone"]},
        headers=harness.mutation_headers(),
    )
    assert invalid.status_code == 409
