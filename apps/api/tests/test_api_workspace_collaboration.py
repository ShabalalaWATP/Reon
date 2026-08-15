"""Routing-workspace collaboration, authority and immutable history."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from conftest import ApiHarness
from mist_service.schemas.workspace_collaboration import WorkspaceRecordCreate
from mist_service.workspace_collaboration_models import WorkspaceRecordEvent


async def _workspace(harness: ApiHarness, username: str, code: str) -> dict:
    await harness.login(username)
    response = await harness.client.get("/api/v1/team-workspaces")
    assert response.status_code == 200
    return next(item for item in response.json()["items"] if item["teamCode"] == code)


async def test_manager_records_handover_and_member_reads_it(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    crioc = await _workspace(harness, "admin74", "CRIOC")
    assert crioc["workspacePosition"] == "MANAGER"
    assert crioc["unitKind"] == "ROOT"
    assert {"QUEUE", "CALENDAR", "PEOPLE", "HANDOVER", "STATISTICS"} <= set(
        crioc["views"]
    )
    create = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records",
        json={
            "grantId": crioc["grantId"],
            "kind": "HANDOVER",
            "title": "Routing handover",
            "body": "Monitor the synthetic priority request during the next shift.",
            "url": "https://products.example.test/handover",
        },
        headers=harness.mutation_headers(),
    )
    assert create.status_code == 200, create.text
    record = create.json()["items"][0]
    assert record["status"] == "OPEN"

    member = await _workspace(harness, "admin75", "CRIOC")
    assert member["workspacePosition"] == "MEMBER"
    listed = await harness.client.get(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records"
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["title"] == "Routing handover"
    denied = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records",
        json={
            "grantId": str(uuid4()),
            "kind": "RISK",
            "title": "Member write",
            "body": "This mutation must remain Manager-only.",
        },
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 404

    crioc = await _workspace(harness, "admin74", "CRIOC")
    resolved = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records/{record['id']}/resolve",
        json={
            "grantId": crioc["grantId"],
            "expectedVersion": record["version"],
            "resolution": "The next shift accepted the routing handover.",
        },
        headers=harness.mutation_headers(),
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["items"][0]["status"] == "RESOLVED"
    async with harness.sessions() as session:
        events = list(
            await session.scalars(
                select(WorkspaceRecordEvent).where(
                    WorkspaceRecordEvent.record_id == UUID(record["id"])
                )
            )
        )
    assert [event.type.value for event in events] == ["CREATED", "RESOLVED"]
    assert [event.record_version for event in events] == [1, 2]


async def test_collaboration_validation_and_stale_resolution_fail_closed(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    crioc = await _workspace(harness, "admin74", "CRIOC")
    invalid = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records",
        json={
            "grantId": crioc["grantId"],
            "kind": "LINK",
            "title": "Unsafe link",
            "body": "Only normal HTTPS links are accepted.",
            "url": "http://example.test/path",
        },
        headers=harness.mutation_headers(),
    )
    assert invalid.status_code == 422
    missing_url = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records",
        json={
            "grantId": crioc["grantId"],
            "kind": "LINK",
            "title": "Missing useful link",
            "body": "A link record must include its HTTPS destination.",
        },
        headers=harness.mutation_headers(),
    )
    assert missing_url.status_code == 422
    forged_grant = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records",
        json={
            "grantId": str(uuid4()),
            "kind": "RISK",
            "title": "Forged authority",
            "body": "A Manager cannot substitute an unrelated management grant.",
        },
        headers=harness.mutation_headers(),
    )
    assert forged_grant.status_code == 404
    missing = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records/{uuid4()}/resolve",
        json={
            "grantId": crioc["grantId"],
            "expectedVersion": 1,
            "resolution": "A missing record cannot be resolved.",
        },
        headers=harness.mutation_headers(),
    )
    assert missing.status_code == 404
    created = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records",
        json={
            "grantId": crioc["grantId"],
            "kind": "DECISION",
            "title": "Bounded decision",
            "body": "This record exercises exact-version resolution behaviour.",
        },
        headers=harness.mutation_headers(),
    )
    record = created.json()["items"][0]
    stale = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records/{record['id']}/resolve",
        json={
            "grantId": crioc["grantId"],
            "expectedVersion": 2,
            "resolution": "A stale version cannot resolve this decision.",
        },
        headers=harness.mutation_headers(),
    )
    assert stale.status_code == 409
    resolved = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records/{record['id']}/resolve",
        json={
            "grantId": crioc["grantId"],
            "expectedVersion": 1,
            "resolution": "The exact current version resolved this decision.",
        },
        headers=harness.mutation_headers(),
    )
    assert resolved.status_code == 200
    repeated = await harness.client.post(
        f"/api/v1/team-workspaces/{crioc['teamId']}/records/{record['id']}/resolve",
        json={
            "grantId": crioc["grantId"],
            "expectedVersion": 2,
            "resolution": "A resolved record cannot be resolved for a second time.",
        },
        headers=harness.mutation_headers(),
    )
    assert repeated.status_code == 404


@pytest.mark.parametrize(
    "url",
    [
        "http://example.test/path",
        "https://user@example.test/path",
        "https://:password@example.test/path",
        "https://example.test/path#fragment",
        "https://example.test\\@127.0.0.1/path",
        "https://example.test:444/path",
        "https://example.test:invalid/path",
        "https://127.0.0.1/path",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/path",
        "https://localhost/path",
        "https://\uff4c\uff4f\uff43\uff41\uff4c\uff48\uff4f\uff53\uff54/path",
        "https://127\u30020\u30020\u30021/path",
        "https://example.test/path\nconfused",
    ],
)
def test_workspace_links_reject_ambiguous_or_private_destinations(url: str) -> None:
    with pytest.raises(ValidationError):
        WorkspaceRecordCreate(
            grantId=uuid4(),
            kind="LINK",
            title="Unsafe destination",
            body="The destination must fail the canonical URL policy.",
            url=url,
        )


def test_workspace_links_are_stored_in_canonical_https_form() -> None:
    command = WorkspaceRecordCreate(
        grantId=uuid4(),
        kind="LINK",
        title="Canonical destination",
        body="The destination is normalised before it reaches persistence.",
        url="HTTPS://Products.Example.Test.:443/handover?view=current",
    )
    assert command.url == ("https://products.example.test/handover?view=current")


def test_workspace_links_reject_invalid_idna(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mist_service.schemas.workspace_collaboration.urlsplit",
        lambda _value: type(
            "Parsed",
            (),
            {
                "port": 443,
                "scheme": "https",
                "hostname": "\ud800.example.test",
                "username": None,
                "password": None,
                "fragment": "",
                "path": "/",
                "query": "",
            },
        )(),
    )
    with pytest.raises(ValueError, match="invalid hostname"):
        WorkspaceRecordCreate(
            grantId=uuid4(),
            kind="LINK",
            title="Invalid international hostname",
            body="Synthetic IDNA failure must be rejected safely.",
            url="https://public.example.test/",
        )
