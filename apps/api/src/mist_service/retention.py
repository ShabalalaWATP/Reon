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

from mist_service.board_models import WorkPackageActivity
from mist_service.models import (
    Base,
    OutboxStatus,
    Session,
    User,
    WorkflowOutbox,
)
from mist_service.operations_models import OperationalRun
from mist_service.request_draft_models import RequestDraft
from mist_service.retention_identity import anonymise_identities, identity_condition
from mist_service.retention_lock import acquire_retention_lock
from mist_service.retention_targets import content_conditions, not_held

APPLY_CONFIRMATION = "APPLY_RETENTION"
DISPOSAL_AUTHORITY = "RETENTION_DISPOSAL"


@dataclass(frozen=True, slots=True)
class DisposalIdentity:
    subject: str
    authority: str

    def validate(self) -> None:
        if not self.subject.strip() or len(self.subject) > 160:
            raise ValueError("a bounded maintenance identity is required")
        if self.authority != DISPOSAL_AUTHORITY:
            raise ValueError("retention disposal authority is required")


@dataclass(frozen=True)
class RetentionPolicy:
    version: str = "v2"
    session_days: int = 30
    draft_days: int = 90
    sent_outbox_days: int = 30
    account_request_days: int = 365
    completed_request_days: int = 2_555
    activity_days: int = 730
    feedback_days: int = 730
    clarification_days: int = 730
    notification_days: int = 180
    product_days: int = 2_555
    access_event_days: int = 730
    security_event_days: int = 730
    identity_days: int = 730
    batch_size: int = 1_000

    def __post_init__(self) -> None:
        periods = (
            self.session_days,
            self.draft_days,
            self.sent_outbox_days,
            self.account_request_days,
            self.completed_request_days,
            self.activity_days,
            self.feedback_days,
            self.clarification_days,
            self.notification_days,
            self.product_days,
            self.access_event_days,
            self.security_event_days,
            self.identity_days,
        )
        if min(periods) < 1:
            raise ValueError("retention periods must be positive")
        if not 1 <= self.batch_size <= 1_000:
            raise ValueError("retention batch size must be between 1 and 1,000")


@dataclass(frozen=True)
class RetentionCounts:
    sessions: int
    drafts: int
    sent_outbox_commands: int
    account_requests: int = 0
    completed_requests: int = 0
    activity_events: int = 0
    feedback: int = 0
    clarifications: int = 0
    notifications: int = 0
    products: int = 0
    access_events: int = 0
    security_events: int = 0
    identities: int = 0


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
    def __init__(
        self, session: AsyncSession, disposal_identity: DisposalIdentity | None = None
    ) -> None:
        self._session = session
        self._disposal_identity = disposal_identity

    async def inspect(
        self, policy: RetentionPolicy, *, now: datetime
    ) -> RetentionCounts:
        session_condition, draft_condition, outbox_condition = _conditions(policy, now)
        counts = RetentionCounts(
            sessions=await self._count(Session, session_condition),
            drafts=await self._count(RequestDraft, draft_condition),
            sent_outbox_commands=await self._count(WorkflowOutbox, outbox_condition),
        )
        return await self._content_counts(policy, now, counts)

    async def apply(self, policy: RetentionPolicy, *, now: datetime) -> RetentionCounts:
        await acquire_retention_lock(self._session)
        session_condition, draft_condition, outbox_condition = _conditions(policy, now)
        base = RetentionCounts(
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
        counts = await self._dispose_content(policy, now, base)
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
                    "legalHoldsApplied": True,
                },
                result_counts={
                    key: value for key, value in asdict(counts).items() if value
                },
            )
        )
        await self._session.flush()
        return counts

    async def _content_counts(
        self, policy: RetentionPolicy, now: datetime, base: RetentionCounts
    ) -> RetentionCounts:
        conditions = content_conditions(policy, now)
        values = {
            name: await self._count(model, condition)
            for name, (model, condition, _id_column) in conditions.items()
        }
        values["activity_events"] += await self._count(
            WorkPackageActivity,
            (
                WorkPackageActivity.created_at
                <= now - timedelta(days=policy.activity_days)
            )
            & not_held("ACTIVITY", WorkPackageActivity.id),
        )
        values["identities"] = await self._count(
            User,
            identity_condition(policy, now),
        )
        return RetentionCounts(**(asdict(base) | values))

    async def _dispose_content(
        self, policy: RetentionPolicy, now: datetime, base: RetentionCounts
    ) -> RetentionCounts:
        conditions = content_conditions(policy, now)
        candidates = {
            name: await self._count(model, condition)
            for name, (model, condition, _id_column) in conditions.items()
        }
        candidates["activity_events"] += await self._count(
            WorkPackageActivity,
            (
                WorkPackageActivity.created_at
                <= now - timedelta(days=policy.activity_days)
            )
            & not_held("ACTIVITY", WorkPackageActivity.id),
        )
        candidates["identities"] = await self._count(
            User, identity_condition(policy, now)
        )
        if any(candidates.values()):
            if self._disposal_identity is None:
                raise ValueError(
                    "a separately authorised disposal identity is required"
                )
            self._disposal_identity.validate()
        if candidates["completed_requests"] or candidates["products"]:
            raise RuntimeError(
                "content disposal requires the approved transactional "
                "object-storage adapter"
            )
        values: dict[str, int] = {}
        # Completed requests and product packages require coordinated external-object
        # erasure. They remain reported as candidates until that adapter is invoked.
        deferred = {"completed_requests", "products"}
        for name, (model, condition, id_column) in conditions.items():
            if name in deferred:
                values[name] = 0
            else:
                values[name] = await self._delete_batch(
                    model, id_column, condition, policy.batch_size
                )
        values["activity_events"] += await self._delete_batch(
            WorkPackageActivity,
            WorkPackageActivity.id,
            (
                WorkPackageActivity.created_at
                <= now - timedelta(days=policy.activity_days)
            )
            & not_held("ACTIVITY", WorkPackageActivity.id),
            policy.batch_size,
        )
        values["identities"] = await anonymise_identities(self._session, policy, now)
        return RetentionCounts(**(asdict(base) | values))

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
