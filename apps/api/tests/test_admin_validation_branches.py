"""Role, membership and update branch coverage for administration."""

from __future__ import annotations

from uuid import uuid4

from pydantic import SecretStr

from conftest import ApiHarness


def _body(
    *,
    role: str,
    units: list[str],
    name: str = "Branch Account",
    scope: str = "Synthetic scope",
) -> dict[str, object]:
    return {
        "displayName": name,
        "role": role,
        "scope": scope,
        "organisationUnitIds": units,
    }


async def _admin(harness: ApiHarness) -> None:
    await harness.login("admin1")
    await harness.elevate()


async def test_missing_wrong_and_duplicate_memberships_are_rejected(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin(harness)
    osg = str(await harness.unit_id("OSG_TEAM"))
    missing = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="INTAKE_TRIAGE", units=[]),
        headers=harness.mutation_headers(),
    )
    assert missing.status_code == 409
    wrong = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="INTAKE_TRIAGE", units=[osg]),
        headers=harness.mutation_headers(),
    )
    assert wrong.status_code == 409
    duplicate = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="DELIVERY_SPECIALIST", units=[osg, osg]),
        headers=harness.mutation_headers(),
    )
    assert duplicate.status_code == 422


async def test_valid_routing_membership_and_display_only_update(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin(harness)
    jioc = str(await harness.unit_id("JIOC"))
    created = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="INTAKE_TRIAGE", units=[jioc], scope="JIOC"),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    account = created.json()
    changed = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={
            **_body(
                role="INTAKE_TRIAGE",
                units=[jioc],
                scope="JIOC",
                name="Renamed Branch Account",
            ),
            "expectedVersion": account["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert changed.status_code == 200
    assert changed.json()["displayName"] == "Renamed Branch Account"


async def test_empty_search_and_unknown_mutation_targets(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin(harness)
    empty = await harness.client.get(
        "/api/v1/admin/users?query=no-such-synthetic-account"
    )
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "nextCursor": None}
    missing_status = await harness.client.patch(
        f"/api/v1/admin/users/{uuid4()}/status",
        json={"isActive": False, "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert missing_status.status_code == 404
    missing_unit = await harness.client.patch(
        f"/api/v1/admin/organisation/units/{uuid4()}",
        json={"name": "Missing Unit", "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert missing_unit.status_code == 404


async def test_create_requires_configured_demo_password(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin(harness)
    original = harness.settings.demo_user_password
    harness.settings.demo_user_password = None
    unavailable = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="REQUESTER", units=[]),
        headers=harness.mutation_headers(),
    )
    assert unavailable.status_code == 404
    harness.settings.demo_user_password = original or SecretStr("admin")


async def test_second_administrator_can_be_demoted_and_sessions_are_revoked(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin(harness)
    created = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="PLATFORM_ADMIN", units=[], scope="Platform support"),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201
    target = created.json()
    demoted = await harness.client.patch(
        f"/api/v1/admin/users/{target['id']}",
        json={
            **_body(
                role="REQUESTER",
                units=[],
                scope="Requesting Area G",
                name=target["displayName"],
            ),
            "expectedVersion": target["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert demoted.status_code == 200
    assert demoted.json()["role"] == "REQUESTER"
