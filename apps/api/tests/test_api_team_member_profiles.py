"""Exact-team colleague-profile API boundaries."""

from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import ApiHarness

pytestmark = pytest.mark.anyio


async def test_colleague_profile_is_bounded_and_private(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin11")
    ssg_id = await harness.unit_id("SSG_TEAM")
    quartz_id = await harness.unit_id("QUARTZ_TEAM")
    analyst_id = await harness.user_id("admin11")

    response = await harness.client.get(
        f"/api/v1/team-workspaces/{ssg_id}/people/{analyst_id}/profile"
    )
    assert response.status_code == 200
    assert response.json() == {
        "accountId": str(analyst_id),
        "name": "Lewis Ferguson",
        "email": "admin11@istari.example.test",
        "role": "DELIVERY_SPECIALIST",
        "teamId": str(ssg_id),
        "teamName": "SSG Team",
        "workspacePosition": "MEMBER",
        "membershipState": "CURRENT",
        "rankOrGrade": None,
        "skills": [],
        "accountActive": True,
    }
    assert "serviceNumber" not in response.json()
    assert "additionalInformation" not in response.json()

    missing = await harness.client.get(
        f"/api/v1/team-workspaces/{ssg_id}/people/{uuid4()}/profile"
    )
    hidden = await harness.client.get(
        f"/api/v1/team-workspaces/{quartz_id}/people/{analyst_id}/profile"
    )
    assert missing.status_code == hidden.status_code == 404
