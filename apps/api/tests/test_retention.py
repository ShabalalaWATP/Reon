"""Safe retention policy, repository and append-only evidence tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from conftest import ApiHarness, request_payload
from mist_service.maintenance import parser
from mist_service.models import OutboxStatus, Session, WorkflowOutbox
from mist_service.operations_models import OperationalRun
from mist_service.request_draft_models import RequestDraft
from mist_service.retention import (
    APPLY_CONFIRMATION,
    RetentionCounts,
    RetentionPolicy,
    RetentionService,
    SqlAlchemyRetentionRepository,
)


class FakeRetentionRepository:
    def __init__(self) -> None:
        self.inspections = 0
        self.applications = 0

    async def inspect(
        self, _policy: RetentionPolicy, *, now: datetime
    ) -> RetentionCounts:
        assert now.tzinfo is not None
        self.inspections += 1
        return RetentionCounts(3, 2, 1)

    async def apply(
        self, _policy: RetentionPolicy, *, now: datetime
    ) -> RetentionCounts:
        assert now.tzinfo is not None
        self.applications += 1
        return RetentionCounts(1, 1, 1)


async def test_retention_defaults_to_dry_run_and_apply_needs_exact_confirmation() -> (
    None
):
    repository = FakeRetentionRepository()
    service = RetentionService(repository)

    report = await service.run()
    assert not report.applied
    assert report.counts == RetentionCounts(3, 2, 1)
    assert repository.inspections == 1

    with pytest.raises(ValueError, match="exact retention confirmation"):
        await service.run(apply=True, confirmation="yes")
    applied = await service.run(apply=True, confirmation=APPLY_CONFIRMATION)
    assert applied.applied
    assert applied.counts == RetentionCounts(1, 1, 1)
    assert repository.applications == 1


@pytest.mark.parametrize(
    "policy",
    [
        {"session_days": 0},
        {"draft_days": 0},
        {"sent_outbox_days": 0},
        {"batch_size": 0},
        {"batch_size": 1_001},
    ],
)
def test_retention_policy_rejects_unbounded_or_non_positive_values(
    policy: dict[str, int],
) -> None:
    with pytest.raises(ValueError):
        RetentionPolicy(**policy)


def test_maintenance_parser_is_dry_run_by_default() -> None:
    dry = parser().parse_args(["retention"])
    assert not dry.apply and dry.confirm is None and dry.batch_size == 1_000
    apply = parser().parse_args(
        ["retention", "--apply", "--confirm", APPLY_CONFIRMATION, "--batch-size", "5"]
    )
    assert apply.apply and apply.confirm == APPLY_CONFIRMATION and apply.batch_size == 5


async def test_repository_deletes_only_eligible_bounded_rows_and_records_counts(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    now = datetime.now(UTC)
    await harness.login("admin2")
    user_id = await harness.user_id("admin2")
    submitted = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert submitted.status_code == 201
    assert await harness.dispatch_start()

    async with harness.sessions() as session, session.begin():
        sent = await session.scalar(select(WorkflowOutbox))
        assert sent is not None
        sent.sent_at = now - timedelta(days=31)
        sent.updated_at = sent.sent_at
        session.add_all(
            [
                Session(
                    user_id=user_id,
                    token_hash=uuid4().hex + uuid4().hex,
                    csrf_token_hash="a" * 64,
                    credential_version=1,
                    last_seen_at=now - timedelta(days=61),
                    expires_at=now - timedelta(days=60),
                ),
                Session(
                    user_id=user_id,
                    token_hash=uuid4().hex + uuid4().hex,
                    csrf_token_hash="b" * 64,
                    credential_version=1,
                    last_seen_at=now - timedelta(days=2),
                    expires_at=now - timedelta(days=1),
                ),
                Session(
                    user_id=user_id,
                    token_hash=uuid4().hex + uuid4().hex,
                    csrf_token_hash="c" * 64,
                    credential_version=1,
                    last_seen_at=now - timedelta(days=61),
                    expires_at=now + timedelta(days=1),
                    revoked_at=now - timedelta(days=31),
                ),
                RequestDraft(
                    requester_id=user_id,
                    title="Old synthetic draft",
                    updated_at=now - timedelta(days=91),
                ),
                RequestDraft(
                    requester_id=user_id,
                    title="Recent synthetic draft",
                    updated_at=now - timedelta(days=1),
                ),
                WorkflowOutbox(
                    request_id=sent.request_id,
                    event_type="RECOVERY_PENDING",
                    payload={},
                    idempotency_key=f"pending:{uuid4()}",
                    status=OutboxStatus.PENDING,
                    available_at=now - timedelta(days=60),
                    updated_at=now - timedelta(days=60),
                ),
            ]
        )

    policy = RetentionPolicy(batch_size=1)
    async with harness.sessions() as session:
        repository = SqlAlchemyRetentionRepository(session)
        dry = await repository.inspect(policy, now=now)
        assert dry == RetentionCounts(2, 1, 1)
        assert await session.scalar(select(OperationalRun)) is None

        applied = await RetentionService(repository).run(
            apply=True,
            confirmation=APPLY_CONFIRMATION,
            policy=policy,
            now=now,
        )
        assert applied.counts == RetentionCounts(1, 1, 1)
        await session.commit()

    async with harness.sessions() as session:
        remaining = await SqlAlchemyRetentionRepository(session).inspect(
            policy, now=now
        )
        assert remaining == RetentionCounts(1, 0, 0)
        evidence = await session.scalar(select(OperationalRun))
        assert evidence is not None
        assert evidence.result_counts == {
            "sessions": 1,
            "drafts": 1,
            "sent_outbox_commands": 1,
        }
        assert "request" not in str(evidence.result_counts).lower()


async def test_operational_run_evidence_is_append_only(api_harness: ApiHarness) -> None:
    harness = api_harness
    async with harness.sessions() as session:
        evidence = OperationalRun(
            job_name="retention",
            policy_version="v1",
            mode="APPLIED",
            criteria={},
            result_counts={},
        )
        session.add(evidence)
        await session.commit()
        evidence_id = evidence.id
        evidence.mode = "ALTERED"
        with pytest.raises(ValueError, match="append-only"):
            await session.flush()
        await session.rollback()
        stored = await session.get(OperationalRun, evidence_id)
        assert stored is not None
        await session.delete(stored)
        with pytest.raises(ValueError, match="append-only"):
            await session.flush()
