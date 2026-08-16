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
    ssg = str(await harness.unit_id("SSG_TEAM"))
    missing = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="INTAKE_TRIAGE", units=[]),
        headers=harness.mutation_headers(),
    )
    assert missing.status_code == 409
    wrong = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="INTAKE_TRIAGE", units=[ssg]),
        headers=harness.mutation_headers(),
    )
    assert wrong.status_code == 409
    duplicate = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="DELIVERY_SPECIALIST", units=[ssg, ssg]),
        headers=harness.mutation_headers(),
    )
    assert duplicate.status_code == 422


async def test_valid_routing_membership_and_display_only_update(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin(harness)
    crioc = str(await harness.unit_id("CRIOC"))
    created = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="INTAKE_TRIAGE", units=[crioc], scope="CRIOC"),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    account = created.json()
    changed = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={
            **_body(
                role="INTAKE_TRIAGE",
                units=[crioc],
                scope="CRIOC",
                name="Renamed Branch Account",
            ),
            "email": "renamed.branch@example.test",
            "expectedVersion": account["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert changed.status_code == 200
    assert changed.json()["displayName"] == "Renamed Branch Account"
    assert changed.json()["email"] == "renamed.branch@example.test"

    # An update may keep the account's own email, but not take another's.
    def _update(email: str, version: int) -> dict[str, object]:
        return {
            **_body(role="INTAKE_TRIAGE", units=[crioc], scope="CRIOC"),
            "email": email,
            "expectedVersion": version,
        }

    taken = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json=_update("admin2@mist.example.test", changed.json()["version"]),
        headers=harness.mutation_headers(),
    )
    assert taken.status_code == 409
    assert "already assigned" in taken.json()["detail"]["message"]
    kept = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json=_update("renamed.branch@example.test", changed.json()["version"]),
        headers=harness.mutation_headers(),
    )
    assert kept.status_code == 200, kept.text


async def test_qc_accounts_require_exact_qc_manager_membership(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _admin(harness)
    ssg = str(await harness.unit_id("SSG_TEAM"))
    qc_team = str(await harness.unit_id("QC_TEAM"))
    options = await harness.client.get("/api/v1/organisation/units")
    assert qc_team in {item["id"] for item in options.json()["items"]}
    wrong = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="QUALITY_RELEASE", units=[ssg]),
        headers=harness.mutation_headers(),
    )
    assert wrong.status_code == 409
    wrong_role = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="DELIVERY_TEAM_LEAD", units=[qc_team]),
        headers=harness.mutation_headers(),
    )
    assert wrong_role.status_code == 409
    created = await harness.client.post(
        "/api/v1/admin/users",
        json=_body(role="QUALITY_RELEASE", units=[qc_team]),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    assert created.json()["memberships"][0]["workspacePosition"] == "MANAGER"
    account = created.json()
    removed = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={
            **_body(role="REQUESTER", units=[], scope="Customer"),
            "expectedVersion": account["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["memberships"] == []
    restored = await harness.client.patch(
        f"/api/v1/admin/users/{account['id']}",
        json={
            **_body(role="QUALITY_RELEASE", units=[qc_team]),
            "expectedVersion": removed.json()["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["memberships"][0]["workspacePosition"] == "MANAGER"


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
