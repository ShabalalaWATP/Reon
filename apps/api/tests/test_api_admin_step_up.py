"""HTTP contract tests for administrator step-up authentication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from conftest import ApiHarness
from istari_service.models import Session


async def _ssg(harness: ApiHarness) -> dict[str, object]:
    response = await harness.client.get("/api/v1/organisation/units")
    assert response.status_code == 200
    return next(item for item in response.json()["items"] if item["code"] == "SSG_TEAM")


async def _rename_noop(harness: ApiHarness, unit: dict[str, object]):
    return await harness.client.patch(
        f"/api/v1/admin/organisation/units/{unit['id']}",
        json={"name": unit["name"], "expectedVersion": unit["version"]},
        headers=harness.mutation_headers(),
    )


async def test_admin_mutations_require_fresh_password_confirmation(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    login = await harness.login("admin1")
    assert login["elevatedUntil"] is None
    unit = await _ssg(harness)

    denied = await _rename_noop(harness, unit)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STEP_UP_REQUIRED"

    elevated = await harness.elevate()
    assert datetime.fromisoformat(elevated["elevatedUntil"]) > datetime.now(UTC)
    current = await harness.client.get("/api/v1/auth/me")
    assert current.status_code == 200
    assert current.json()["elevatedUntil"] == elevated["elevatedUntil"]
    harness.csrf_token = current.json()["csrfToken"]
    assert (await _rename_noop(harness, unit)).status_code == 200


async def test_expired_elevation_is_rejected_and_is_bound_to_the_session(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin1")
    await harness.elevate()
    unit = await _ssg(harness)
    async with harness.sessions() as session, session.begin():
        active = await session.scalar(
            select(Session).where(Session.revoked_at.is_(None))
        )
        assert active is not None
        active.elevated_until = datetime.now(UTC) - timedelta(seconds=1)

    expired = await _rename_noop(harness, unit)
    assert expired.status_code == 403
    assert expired.json()["detail"]["code"] == "STEP_UP_REQUIRED"

    relogin = await harness.login("admin1")
    assert relogin["elevatedUntil"] is None
    assert (await _rename_noop(harness, unit)).status_code == 403


async def test_step_up_rejects_wrong_password_non_admin_and_missing_csrf(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin1")
    wrong = await harness.client.post(
        "/api/v1/auth/elevate",
        json={"password": "incorrect"},
        headers=harness.mutation_headers(),
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"]["code"] == "AUTHENTICATION_FAILED"
    no_csrf = await harness.client.post(
        "/api/v1/auth/elevate",
        json={"password": "admin"},
    )
    assert no_csrf.status_code == 403

    await harness.login("admin2")
    non_admin = await harness.client.post(
        "/api/v1/auth/elevate",
        json={"password": "admin"},
        headers=harness.mutation_headers(),
    )
    assert non_admin.status_code == 403
    assert non_admin.json()["detail"]["code"] == "ADMINISTRATION_ACCESS_DENIED"
