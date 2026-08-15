"""Customer draft, strict submission and retry behaviour through the public API."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from conftest import ApiHarness, request_payload
from mist_service.domain import Actor
from mist_service.errors import ObjectNotFound
from mist_service.models import ServiceRequest, UserRole
from mist_service.repositories.requests import SqlAlchemyRequestRepository
from mist_service.schemas.drafts import RequestDraftCreate
from mist_service.services.draft_service import DraftService


@pytest.mark.asyncio
async def test_customer_draft_lifecycle_and_idempotent_submission(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    empty = await harness.client.get("/api/v1/request-drafts")
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "nextCursor": None}

    internal_route_field = await harness.client.post(
        "/api/v1/request-drafts",
        json={"requestingBusinessArea": "Requesting Area B"},
        headers=harness.mutation_headers(),
    )
    assert internal_route_field.status_code == 422

    created = await harness.client.post(
        "/api/v1/request-drafts",
        json={"title": "Early service need"},
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    draft_id = draft["id"]
    assert "requestingBusinessArea" not in draft
    assert draft["version"] == 1

    listed = await harness.client.get("/api/v1/request-drafts")
    assert [item["id"] for item in listed.json()["items"]] == [draft_id]
    assert (await harness.client.get(f"/api/v1/request-drafts/{draft_id}")).json()[
        "title"
    ] == "Early service need"

    await harness.login("admin3")
    assert (
        await harness.client.get(f"/api/v1/request-drafts/{draft_id}")
    ).status_code == 404
    assert (
        await harness.client.patch(
            f"/api/v1/request-drafts/{draft_id}",
            json={"expectedVersion": 1, "title": "Cross-Customer edit"},
            headers=harness.mutation_headers(),
        )
    ).status_code == 404

    await harness.login("admin2")
    invalid_supporting_information = await harness.client.patch(
        f"/api/v1/request-drafts/{draft_id}",
        json={
            "expectedVersion": 1,
            "supportingInformation": "x" * 2001,
        },
        headers=harness.mutation_headers(),
    )
    assert invalid_supporting_information.status_code == 422
    stale = await harness.client.patch(
        f"/api/v1/request-drafts/{draft_id}",
        json={"expectedVersion": 9, "title": "Stale edit"},
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409

    updated = await harness.client.patch(
        f"/api/v1/request-drafts/{draft_id}",
        json={
            "expectedVersion": 1,
            "title": "",
            "description": "An incomplete private draft.",
            "supportingInformation": "",
        },
        headers=harness.mutation_headers(),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["title"] == ""

    incomplete = await harness.client.post(
        f"/api/v1/request-drafts/{draft_id}/submit",
        json={"expectedVersion": 2, "title": "Still incomplete"},
        headers=harness.mutation_headers(),
    )
    assert incomplete.status_code == 422

    submission_key = str(uuid4())
    submission = {
        **request_payload(),
        "expectedVersion": 2,
        "submissionKey": submission_key,
    }
    stale_submission = await harness.client.post(
        f"/api/v1/request-drafts/{draft_id}/submit",
        json={**submission, "expectedVersion": 1},
        headers=harness.mutation_headers(),
    )
    assert stale_submission.status_code == 409
    internal_route_field = await harness.client.post(
        f"/api/v1/request-drafts/{draft_id}/submit",
        json={**submission, "requestingBusinessArea": "Requesting Area B"},
        headers=harness.mutation_headers(),
    )
    assert internal_route_field.status_code == 422
    submitted = await harness.client.post(
        f"/api/v1/request-drafts/{draft_id}/submit",
        json=submission,
        headers=harness.mutation_headers(),
    )
    assert submitted.status_code == 200, submitted.text
    request_id = submitted.json()["id"]
    assert submitted.json()["productAvailable"] is False
    assert submitted.json()["feedbackSubmitted"] is False

    repeated = await harness.client.post(
        f"/api/v1/request-drafts/{draft_id}/submit",
        json=submission,
        headers=harness.mutation_headers(),
    )
    assert repeated.status_code == 200
    assert repeated.json()["id"] == request_id
    assert (await harness.client.get("/api/v1/request-drafts")).json() == {
        "items": [],
        "nextCursor": None,
    }
    requests = (await harness.client.get("/api/v1/requests")).json()["items"]
    assert [item["id"] for item in requests] == [request_id]


@pytest.mark.asyncio
async def test_customer_can_delete_only_current_private_draft(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin2")
    created = await harness.client.post(
        "/api/v1/request-drafts",
        json={},
        headers=harness.mutation_headers(),
    )
    draft = created.json()
    stale = await harness.client.delete(
        f"/api/v1/request-drafts/{draft['id']}?expectedVersion=2",
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409
    deleted = await harness.client.delete(
        f"/api/v1/request-drafts/{draft['id']}?expectedVersion=1",
        headers=harness.mutation_headers(),
    )
    assert deleted.status_code == 204
    assert (
        await harness.client.get(f"/api/v1/request-drafts/{draft['id']}")
    ).status_code == 404


@pytest.mark.asyncio
async def test_submission_key_is_owned_and_retries_one_request(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    submission_key = str(uuid4())
    payload = request_payload(submissionKey=submission_key)
    await harness.login("admin2")
    first = await harness.client.post(
        "/api/v1/requests", json=payload, headers=harness.mutation_headers()
    )
    repeated = await harness.client.post(
        "/api/v1/requests", json=payload, headers=harness.mutation_headers()
    )
    assert first.status_code == repeated.status_code == 201
    assert first.json()["id"] == repeated.json()["id"]

    await harness.login("admin3")
    concealed = await harness.client.post(
        "/api/v1/requests",
        json=payload,
        headers=harness.mutation_headers(),
    )
    assert concealed.status_code == 404


@pytest.mark.asyncio
async def test_racing_submission_key_returns_the_original_request(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A duplicate that slips past the pre-check stays idempotent, not a 500."""

    harness = api_harness
    submission_key = str(uuid4())
    payload = request_payload(submissionKey=submission_key)
    await harness.login("admin2")
    first = await harness.client.post(
        "/api/v1/requests", json=payload, headers=harness.mutation_headers()
    )
    assert first.status_code == 201

    original = SqlAlchemyRequestRepository._request_for_submission_key
    calls = {"count": 0}

    async def blind_precheck(
        self: SqlAlchemyRequestRepository, key: UUID
    ) -> ServiceRequest | None:
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return await original(self, key)

    monkeypatch.setattr(
        SqlAlchemyRequestRepository, "_request_for_submission_key", blind_precheck
    )
    raced = await harness.client.post(
        "/api/v1/requests", json=payload, headers=harness.mutation_headers()
    )

    assert raced.status_code == 201
    assert raced.json()["id"] == first.json()["id"]
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_draft_schema_and_non_customer_service_edges() -> None:
    draft = RequestDraftCreate(supporting_information=None)
    assert draft.supporting_information is None
    with pytest.raises(ValidationError):
        RequestDraftCreate(supporting_information="x" * 2001)

    staff = Actor(
        uuid4(),
        "staff@example.test",
        "Synthetic Staff",
        UserRole.INTAKE_TRIAGE,
        "CRIOC",
    )
    service = DraftService(object())  # type: ignore[arg-type]
    with pytest.raises(ObjectNotFound):
        await service.list(staff)
