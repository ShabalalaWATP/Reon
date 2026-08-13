"""Legal-hold, authorised disposal and security-event edge tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

import istari_service.retention as retention_module
from api_helpers import submit_request
from conftest import ApiHarness
from istari_service.clarification_models import (
    ClarificationMessage,
    ClarificationMessageKind,
    ClarificationStatus,
    ClarificationThread,
)
from istari_service.compliance_models import SecurityEvent, SecurityOutcome
from istari_service.legal_holds import LEGAL_HOLD_AUTHORITY, LegalHoldService
from istari_service.models import ServiceRequest
from istari_service.retention import (
    DISPOSAL_AUTHORITY,
    DisposalIdentity,
    RetentionCounts,
    RetentionPolicy,
    SqlAlchemyRetentionRepository,
)
from istari_service.security_events import SecurityEventCommand, SecurityEventRecorder


async def test_legal_hold_lifecycle_and_authority(api_harness: ApiHarness) -> None:
    async with api_harness.sessions() as session, session.begin():
        with pytest.raises(ValueError, match="authority"):
            LegalHoldService(session, subject="operator", authority="PLATFORM_ADMIN")
        service = LegalHoldService(
            session, subject="synthetic-counsel", authority=LEGAL_HOLD_AUTHORITY
        )
        with pytest.raises(LookupError, match="target was not found"):
            await service.apply("REQUEST", uuid4(), "LITIGATION")
        target = await api_harness.user_id("admin2")
        hold = await service.apply("IDENTITY", target, "LITIGATION")
        assert hold.authorised_by == "synthetic-counsel"
        released = await service.release("IDENTITY", target)
        assert released.released_at is not None
        released.reason_code = "ALTERED"
        with pytest.raises(ValueError, match="immutable"):
            await session.flush()


async def test_legal_hold_release_is_one_way(api_harness: ApiHarness) -> None:
    async with api_harness.sessions() as session, session.begin():
        service = LegalHoldService(
            session, subject="synthetic-counsel", authority=LEGAL_HOLD_AUTHORITY
        )
        target = await api_harness.user_id("admin2")
        await service.apply("IDENTITY", target, "LITIGATION")
        released = await service.release("IDENTITY", target)
        await session.flush()
        released.released_by = "different-counsel"
        with pytest.raises(ValueError, match="legal-hold release"):
            await session.flush()


@pytest.mark.parametrize("subject", ["", "x" * 161])
async def test_legal_hold_rejects_invalid_subject(
    api_harness: ApiHarness, subject: str
) -> None:
    async with api_harness.sessions() as session:
        with pytest.raises(ValueError, match="identity"):
            LegalHoldService(session, subject=subject, authority=LEGAL_HOLD_AUTHORITY)


async def test_legal_hold_rejects_invalid_target_and_missing_release(
    api_harness: ApiHarness,
) -> None:
    async with api_harness.sessions() as session, session.begin():
        service = LegalHoldService(
            session, subject="synthetic-counsel", authority=LEGAL_HOLD_AUTHORITY
        )
        for target_type, target_id, reason, message in (
            ("UNKNOWN", str(uuid4()), "LITIGATION", "target type"),
            ("REQUEST", "not-a-uuid", "LITIGATION", "target ID"),
            ("REQUEST", str(uuid4()), "", "reason code"),
        ):
            with pytest.raises(ValueError, match=message):
                await service.apply(target_type, target_id, reason)
        with pytest.raises(LookupError, match="not found"):
            await service.release("REQUEST", uuid4())


@pytest.mark.parametrize(
    ("identity", "message"),
    [
        (DisposalIdentity("", DISPOSAL_AUTHORITY), "maintenance identity"),
        (DisposalIdentity("x" * 161, DISPOSAL_AUTHORITY), "maintenance identity"),
        (DisposalIdentity("operator", "PLATFORM_ADMIN"), "disposal authority"),
    ],
)
def test_disposal_identity_validation(identity: DisposalIdentity, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        identity.validate()


def _targets(*names: str) -> dict[str, tuple[object, object, object]]:
    requested = {
        name: (SecurityEvent, SecurityEvent.created_at.is_not(None), SecurityEvent.id)
        for name in names
    }
    requested["activity_events"] = (
        SecurityEvent,
        SecurityEvent.created_at.is_(None),
        SecurityEvent.id,
    )
    return requested


async def _one() -> int:
    return 1


@pytest.mark.parametrize(
    ("identity", "names", "message"),
    [
        (None, ("feedback",), "separately authorised"),
        (
            DisposalIdentity("operator", DISPOSAL_AUTHORITY),
            ("completed_requests", "products"),
            "object-storage adapter",
        ),
    ],
)
async def test_content_disposal_fails_closed(
    api_harness: ApiHarness,
    monkeypatch: pytest.MonkeyPatch,
    identity: DisposalIdentity | None,
    names: tuple[str, ...],
    message: str,
) -> None:
    async with api_harness.sessions() as session:
        repository = SqlAlchemyRetentionRepository(session, identity)
        monkeypatch.setattr(
            retention_module, "content_conditions", lambda _p, _n: _targets(*names)
        )
        monkeypatch.setattr(repository, "_count", lambda _m, _c: _one())
        with pytest.raises((ValueError, RuntimeError), match=message):
            await repository._dispose_content(
                RetentionPolicy(), datetime.now(UTC), RetentionCounts(0, 0, 0)
            )


async def test_clarification_disposal_uses_parent_cascade(
    api_harness: ApiHarness,
) -> None:
    request_id = UUID(await submit_request(api_harness))
    now = datetime.now(UTC)
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        thread = ClarificationThread(
            request_id=request_id,
            sequence=1,
            requested_by_user_id=request.requester_id,
            assigned_specialist_id=request.requester_id,
            question="Synthetic question",
            reason="Synthetic reason",
            response_deadline=now.date(),
            status=ClarificationStatus.ANSWERED,
            closed_at=now - timedelta(days=2),
        )
        session.add(thread)
        await session.flush()
        session.add(
            ClarificationMessage(
                thread_id=thread.id,
                actor_user_id=request.requester_id,
                sequence=1,
                kind=ClarificationMessageKind.REQUEST,
                body="Synthetic message",
            )
        )
        await session.flush()
        counts = await SqlAlchemyRetentionRepository(
            session, DisposalIdentity("operator", DISPOSAL_AUTHORITY)
        )._dispose_content(
            RetentionPolicy(clarification_days=1),
            now,
            RetentionCounts(0, 0, 0),
        )
        assert counts.clarifications == 1
        # SQLite foreign keys are not enabled in this generic harness. Production
        # migration 0039 makes this parent delete cascade atomically.
        assert await session.scalar(select(func.count(ClarificationThread.id))) == 0
        assert await session.get(ClarificationThread, thread.id) is None


async def test_security_event_hashes_identifiers(api_harness: ApiHarness) -> None:
    recorder = SecurityEventRecorder(api_harness.sessions, pseudonym_key=b"s" * 32)
    await recorder.record(
        SecurityEventCommand(
            "LOGIN",
            SecurityOutcome.FAILURE,
            "INVALID_CREDENTIALS",
            subject="Example.User",
            source="192.0.2.10",
        )
    )
    async with api_harness.sessions() as session:
        event = await session.scalar(select(SecurityEvent))
        assert event is not None
        assert event.subject_hash != "Example.User"
        assert event.source_hash != "192.0.2.10"


async def test_authenticated_denial_deduplicates_across_sources(
    api_harness: ApiHarness,
) -> None:
    recorder = SecurityEventRecorder(api_harness.sessions, pseudonym_key=b"s" * 32)
    actor_id = await api_harness.user_id("admin3")
    common = {
        "event_type": "AUTHORIZATION_DENIAL",
        "outcome": SecurityOutcome.DENIED,
        "reason_code": "NOT_FOUND",
        "actor_user_id": actor_id,
        "request_method": "POST",
        "route_template": "/work-items/{work_id}/claim",
    }
    assert await recorder.record_once(
        SecurityEventCommand(**common, source="198.51.100.1")
    )
    assert not await recorder.record_once(
        SecurityEventCommand(**common, source="203.0.113.2")
    )

    async with api_harness.sessions() as session:
        events = list(
            await session.scalars(
                select(SecurityEvent).where(
                    SecurityEvent.event_type == "AUTHORIZATION_DENIAL",
                    SecurityEvent.actor_user_id == actor_id,
                    SecurityEvent.route_template == "/work-items/{work_id}/claim",
                )
            )
        )
    assert len(events) == 1
    assert events[0].source_hash is not None


def test_security_event_rejects_short_key(api_harness: ApiHarness) -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        SecurityEventRecorder(api_harness.sessions, pseudonym_key=b"short")


@pytest.mark.parametrize(
    "command",
    [
        SecurityEventCommand("", SecurityOutcome.DENIED, "REASON"),
        SecurityEventCommand("LOGIN", SecurityOutcome.DENIED, ""),
        SecurityEventCommand(
            "LOGIN", SecurityOutcome.DENIED, "R", correlation_id="x" * 81
        ),
        SecurityEventCommand(
            "LOGIN", SecurityOutcome.DENIED, "R", request_method="x" * 11
        ),
        SecurityEventCommand(
            "LOGIN", SecurityOutcome.DENIED, "R", route_template="x" * 161
        ),
    ],
)
async def test_security_event_rejects_invalid_command(
    api_harness: ApiHarness, command: SecurityEventCommand
) -> None:
    recorder = SecurityEventRecorder(api_harness.sessions, pseudonym_key=b"s" * 32)
    with pytest.raises(ValueError, match="security-event"):
        await recorder.record(command)
