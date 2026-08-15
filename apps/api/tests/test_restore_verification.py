"""Content-free restored database verification tests."""

from __future__ import annotations

from sqlalchemy import text, update

from conftest import ApiHarness, request_payload
from mist_service.request_event_models import RequestEvent
from mist_service.restore_verification import verify_restored_database


async def _seed_revision(harness: ApiHarness, revision: str) -> None:
    async with harness.sessions() as session, session.begin():
        await session.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(64))")
        )
        await session.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": revision},
        )


async def test_restore_verification_reports_only_counts_revision_and_integrity(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    revision = "0011_operational_evidence"
    await _seed_revision(harness, revision)
    await harness.login("admin2")
    submitted = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert submitted.status_code == 201

    async with harness.sessions() as session:
        report = await verify_restored_database(
            session,
            expected_revision=revision,
        )

    assert report.valid
    assert report.schema_revision == revision
    assert report.users == 100
    assert report.requests == 1
    assert report.request_events == 1
    assert report.pending_commands == 1
    assert report.request_audit_valid and report.admin_audit_valid
    assert not hasattr(report, "request_titles")


async def test_restore_verification_fails_wrong_revision_or_tampered_chain(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await _seed_revision(harness, "0011_operational_evidence")
    await harness.login("admin2")
    assert (
        await harness.client.post(
            "/api/v1/requests",
            json=request_payload(),
            headers=harness.mutation_headers(),
        )
    ).status_code == 201
    async with harness.sessions() as session:
        await session.execute(
            update(RequestEvent).values(message="Tampered synthetic event")
        )
        await session.commit()

    async with harness.sessions() as session:
        report = await verify_restored_database(
            session,
            expected_revision="unexpected_revision",
        )
    assert not report.valid
    assert not report.request_audit_valid
    assert report.admin_audit_valid
