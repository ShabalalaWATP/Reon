"""Authenticated self-profile API behaviour."""

from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import ApiHarness
from istari_service.errors import ObjectNotFound
from istari_service.repositories.profiles import SqlAlchemyProfileRepository
from istari_service.schemas.profiles import _plain_optional


async def test_authenticated_user_can_maintain_only_their_profile(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    initial = await harness.client.get("/api/v1/profile")
    assert initial.status_code == 200
    assert initial.json() == {
        "userId": str(await harness.user_id("admin2")),
        "name": "John McGinn",
        "username": "admin2",
        "email": "admin2@istari.example.test",
        "role": "REQUESTER",
        "profileTeam": None,
        "rankOrGrade": None,
        "serviceNumber": None,
        "additionalInformation": None,
        "version": 1,
    }

    saved = await harness.client.patch(
        "/api/v1/profile",
        json={
            "profileTeam": "Fictional Customer Team",
            "rankOrGrade": "Grade 7",
            "serviceNumber": "SYN-1042",
            "additionalInformation": "Synthetic profile context.",
            "expectedVersion": 1,
        },
        headers=harness.mutation_headers(),
    )
    assert saved.status_code == 200
    assert saved.json()["version"] == 2
    assert saved.json()["profileTeam"] == "Fictional Customer Team"

    stale = await harness.client.patch(
        "/api/v1/profile",
        json={"profileTeam": None, "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409
    no_csrf = await harness.client.patch(
        "/api/v1/profile",
        json={"profileTeam": None, "expectedVersion": 2},
    )
    assert no_csrf.status_code == 403

    await harness.login("admin3")
    other = await harness.client.get("/api/v1/profile")
    assert other.status_code == 200
    assert other.json()["profileTeam"] is None


async def test_profile_rejects_unsafe_or_unrecognised_input(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    unsafe = await harness.client.patch(
        "/api/v1/profile",
        json={"serviceNumber": "SYN\u202e1042", "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert unsafe.status_code == 422
    extra = await harness.client.patch(
        "/api/v1/profile",
        json={"nickname": "Not accepted", "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert extra.status_code == 422

    assert _plain_optional("   ", maximum=10) is None
    with pytest.raises(ValueError, match="must not exceed"):
        _plain_optional("too long", maximum=3)
    async with harness.sessions() as session:
        with pytest.raises(ObjectNotFound):
            await SqlAlchemyProfileRepository(session).view(uuid4())
