"""Bounded, content-free retention inspection and application."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from istari_service.models import Base, OutboxStatus, Session, WorkflowOutbox
from istari_service.operations_models import OperationalRun
from istari_service.request_draft_models import RequestDraft

APPLY_CONFIRMATION = "APPLY_RETENTION"


@dataclass(frozen=True)
class RetentionPolicy:
    version: str = "v1"
    session_days: int = 30
    draft_days: int = 90
    sent_outbox_days: int = 30
    batch_size: int = 1_000

    def __post_init__(self) -> None:
        if min(self.session_days, self.draft_days, self.sent_outbox_days) < 1:
            raise ValueError("retention periods must be positive")
        if not 1 <= self.batch_size <= 1_000:
            raise ValueError("retention batch size must be between 1 and 1,000")


@dataclass(frozen=True)
class RetentionCounts:
    sessions: int
    drafts: int
    sent_outbox_commands: int


@dataclass(frozen=True)
class RetentionReport:
    applied: bool
    policy_version: str
    evaluated_at: datetime
    counts: RetentionCounts


class RetentionPort(Protocol):
    async def inspect(
        self, policy: RetentionPolicy, *, now: datetime
    ) -> RetentionCounts: ...

    async def apply(
        self, policy: RetentionPolicy, *, now: datetime
    ) -> RetentionCounts: ...


class RetentionService:
    def __init__(self, repository: RetentionPort) -> None:
        self._repository = repository

    async def run(
        self,
        *,
        apply: bool = False,
        confirmation: str | None = None,
        policy: RetentionPolicy | None = None,
        now: datetime | None = None,
    ) -> RetentionReport:
        selected = policy or RetentionPolicy()
        evaluated_at = now or datetime.now(UTC)
        if apply and confirmation != APPLY_CONFIRMATION:
            raise ValueError("exact retention confirmation is required")
        counts = (
            await self._repository.apply(selected, now=evaluated_at)
            if apply
            else await self._repository.inspect(selected, now=evaluated_at)
        )
        return RetentionReport(apply, selected.version, evaluated_at, counts)


class SqlAlchemyRetentionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def inspect(
        self, policy: RetentionPolicy, *, now: datetime
    ) -> RetentionCounts:
        session_condition, draft_condition, outbox_condition = _conditions(policy, now)
        return RetentionCounts(
            sessions=await self._count(Session, session_condition),
            drafts=await self._count(RequestDraft, draft_condition),
            sent_outbox_commands=await self._count(WorkflowOutbox, outbox_condition),
        )

    async def apply(self, policy: RetentionPolicy, *, now: datetime) -> RetentionCounts:
        session_condition, draft_condition, outbox_condition = _conditions(policy, now)
        counts = RetentionCounts(
            sessions=await self._delete_batch(
                Session, Session.id, session_condition, policy.batch_size
            ),
            drafts=await self._delete_batch(
                RequestDraft, RequestDraft.id, draft_condition, policy.batch_size
            ),
            sent_outbox_commands=await self._delete_batch(
                WorkflowOutbox,
                WorkflowOutbox.id,
                outbox_condition,
                policy.batch_size,
            ),
        )
        self._session.add(
            OperationalRun(
                job_name="retention",
                policy_version=policy.version,
                mode="APPLIED",
                criteria={
                    "sessionDays": policy.session_days,
                    "draftDays": policy.draft_days,
                    "sentOutboxDays": policy.sent_outbox_days,
                    "batchSize": policy.batch_size,
                },
                result_counts=asdict(counts),
            )
        )
        await self._session.flush()
        return counts

    async def _count(self, model: type[Base], condition: ColumnElement[bool]) -> int:
        value = await self._session.scalar(
            select(func.count()).select_from(model).where(condition)
        )
        return int(value or 0)

    async def _delete_batch(
        self,
        model: type[Base],
        id_column: InstrumentedAttribute[UUID],
        condition: ColumnElement[bool],
        batch_size: int,
    ) -> int:
        ids = list(
            await self._session.scalars(
                select(id_column).where(condition).order_by(id_column).limit(batch_size)
            )
        )
        if not ids:
            return 0
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                delete(model).where(id_column.in_(ids), condition)
            ),
        )
        return int(result.rowcount or 0)


def _conditions(
    policy: RetentionPolicy, now: datetime
) -> tuple[ColumnElement[bool], ColumnElement[bool], ColumnElement[bool]]:
    session_cutoff = now - timedelta(days=policy.session_days)
    draft_cutoff = now - timedelta(days=policy.draft_days)
    outbox_cutoff = now - timedelta(days=policy.sent_outbox_days)
    return (
        or_(
            Session.expires_at <= session_cutoff,
            Session.revoked_at <= session_cutoff,
        ),
        RequestDraft.updated_at <= draft_cutoff,
        (
            (WorkflowOutbox.status == OutboxStatus.SENT)
            & (WorkflowOutbox.sent_at <= outbox_cutoff)
        ),
    )
