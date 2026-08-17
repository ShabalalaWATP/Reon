"""Public account-request and stepped-up administrator review journeys."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import select

from conftest import ApiHarness
from mist_service.account_request_models import AccountRequest
from mist_service.config import Environment, Settings
from mist_service.errors import AdministrationUnavailable
from mist_service.models import User, UserRole
from mist_service.repositories.account_requests import (
    SqlAlchemyAccountRequestRepository,
)
from mist_service.schemas.account_requests import AccountRequestCreate
from mist_service.services.account_request_service import AccountRequestService


async def test_account_requests_are_generic_and_reviewed_by_an_administrator(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    payload = {
        "displayName": "Synthetic Customer",
        "contactEmail": "CUSTOMER@example.test",
        "reason": "I need access for a fictional service request.",
    }
    first = await harness.client.post("/api/v1/auth/account-requests", json=payload)
    duplicate = await harness.client.post("/api/v1/auth/account-requests", json=payload)
    assert first.status_code == duplicate.status_code == 202
    assert first.json() == duplicate.json() == {"status": "pending"}

    await harness.login("admin1")
    listed = await harness.client.get("/api/v1/admin/account-requests")
    assert listed.status_code == 200
    request = listed.json()["items"][0]
    assert request["contactEmail"] == "customer@example.test"

    denied = await harness.client.post(
        f"/api/v1/admin/account-requests/{request['id']}/approve",
        json={"expectedVersion": request["version"]},
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 403
    await harness.elevate()
    approved = await harness.client.post(
        f"/api/v1/admin/account-requests/{request['id']}/approve",
        json={"expectedVersion": request["version"]},
        headers=harness.mutation_headers(),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    async with harness.sessions() as session:
        user = await session.scalar(
            select(User).where(User.id == UUID(approved.json()["createdUserId"]))
        )
        assert user is not None
        assert user.role is UserRole.REQUESTER
        assert user.username.startswith("admin")


async def test_account_request_rejection_requires_a_reason_and_current_version(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    created = await harness.client.post(
        "/api/v1/auth/account-requests",
        json={
            "displayName": "Second Customer",
            "contactEmail": "second@example.test",
            "reason": "I need access for another fictional request.",
        },
    )
    assert created.status_code == 202
    await harness.login("admin1")
    await harness.elevate()
    rows = (await harness.client.get("/api/v1/admin/account-requests")).json()["items"]
    request = next(row for row in rows if row["contactEmail"] == "second@example.test")
    invalid = await harness.client.post(
        f"/api/v1/admin/account-requests/{request['id']}/reject",
        json={"decisionNote": "", "expectedVersion": request["version"]},
        headers=harness.mutation_headers(),
    )
    assert invalid.status_code == 422
    rejected = await harness.client.post(
        f"/api/v1/admin/account-requests/{request['id']}/reject",
        json={
            "decisionNote": "Access need not established.",
            "expectedVersion": request["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    stale = await harness.client.post(
        f"/api/v1/admin/account-requests/{request['id']}/reject",
        json={
            "decisionNote": "Repeated decision.",
            "expectedVersion": request["version"],
        },
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409
    async with harness.sessions() as session:
        stored = await session.get(AccountRequest, UUID(request["id"]))
        assert stored is not None
        assert stored.decision_note == "Access need not established."


async def test_account_request_input_is_strict(api_harness: ApiHarness) -> None:
    invalid = await api_harness.client.post(
        "/api/v1/auth/account-requests",
        json={"displayName": " ", "contactEmail": "not-an-email", "reason": "short"},
    )
    assert invalid.status_code == 422


@pytest.mark.parametrize(
    "contact_email",
    (
        "recipient@example.test?bcc=attacker%40example.test",
        "recipient@example.test#fragment",
        "recipient@example.test%0d%0abcc:attacker@example.test",
        "recipient @example.test",
    ),
)
async def test_account_request_rejects_mailto_field_injection(
    api_harness: ApiHarness,
    contact_email: str,
) -> None:
    response = await api_harness.client.post(
        "/api/v1/auth/account-requests",
        json={
            "displayName": "Synthetic Customer",
            "contactEmail": contact_email,
            "reason": "I need access for a fictional service request.",
        },
    )
    assert response.status_code == 422


async def test_account_requests_are_unavailable_when_demo_accounts_are_disabled() -> (
    None
):
    repository = AsyncMock(spec=SqlAlchemyAccountRequestRepository)
    service = AccountRequestService(
        repository,
        Settings(
            environment=Environment.TEST,
            database_url="sqlite+aiosqlite:///:memory:",
            allow_demo_users=False,
        ),
    )

    with pytest.raises(AdministrationUnavailable):
        await service.submit(
            AccountRequestCreate(
                display_name="Synthetic Customer",
                contact_email="synthetic@example.test",
                reason="I need access for a fictional service request.",
            )
        )
    repository.submit.assert_not_awaited()
