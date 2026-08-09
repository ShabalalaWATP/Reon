"""Repeatable statement-count and contention measurements at target scale."""

from __future__ import annotations

import asyncio
from base64 import urlsafe_b64encode
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy import Select, event, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from istari_service.board_models import WorkPackage
from istari_service.models import RequestEvent, ServiceRequest, User, WorkflowTask
from istari_service.organisation_models import OrganisationUnit
from istari_service.repositories.admin import SqlAlchemyAdminRepository
from istari_service.repositories.auth import SqlAlchemyAuthRepository
from istari_service.repositories.board import SqlAlchemyBoardRepository
from istari_service.repositories.drafts import SqlAlchemyDraftRepository
from istari_service.repositories.organisation import SqlAlchemyOrganisationRepository
from istari_service.repositories.projection_pagination import encode_cursor
from istari_service.repositories.requests import SqlAlchemyRequestRepository
from istari_service.repositories.work import SqlAlchemyWorkRepository
from istari_service.request_draft_models import RequestDraft
from istari_service.schemas.board import BoardFilters, BoardItemType
from istari_service.worker_runtime import MaintenanceJob, WorkerIteration

SessionFactory = async_sessionmaker[AsyncSession]
MeasuredCall = Callable[[AsyncSession], Awaitable[object]]


@dataclass(frozen=True, slots=True)
class ScaleContext:
    requester_id: UUID
    request_id: UUID
    osg_team_id: UUID
    triage_actor: Any
    request_cursor: str
    draft_cursor: str
    work_cursor: str
    user_cursor: str
    board_cursor: str
    history_cursor: str


class StatementCounter:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.enabled = False
        self.statements: list[str] = []
        event.listen(engine.sync_engine, "before_cursor_execute", self._record)

    def _record(
        self,
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _many: object,
    ) -> None:
        if self.enabled:
            self.statements.append(statement.lstrip().split(None, 1)[0].upper())

    def start(self) -> None:
        self.statements.clear()
        self.enabled = True

    def stop(self) -> list[str]:
        self.enabled = False
        return list(self.statements)

    def close(self) -> None:
        event.remove(self.engine.sync_engine, "before_cursor_execute", self._record)


async def load_scale_context(
    sessions: SessionFactory,
    *,
    depth: int,
) -> ScaleContext:
    async with sessions() as session:
        requester = await session.scalar(select(User).where(User.username == "admin2"))
        triage = await SqlAlchemyAuthRepository(session).find_account("admin4")
        osg_team_id = await session.scalar(
            select(OrganisationUnit.id).where(OrganisationUnit.code == "OSG_TEAM")
        )
        request_id = await session.scalar(
            select(ServiceRequest.id).where(ServiceRequest.reference == "PERF-000001")
        )
        if (
            requester is None
            or triage is None
            or osg_team_id is None
            or request_id is None
        ):
            raise RuntimeError("the target-scale baseline has not been seeded")
        return ScaleContext(
            requester_id=requester.id,
            request_id=request_id,
            osg_team_id=osg_team_id,
            triage_actor=triage.actor,
            request_cursor=await _cursor_at(
                session,
                select(ServiceRequest.updated_at, ServiceRequest.id).where(
                    ServiceRequest.requester_id == requester.id
                ),
                ServiceRequest.updated_at,
                ServiceRequest.id,
                depth,
            ),
            draft_cursor=await _cursor_at(
                session,
                select(RequestDraft.updated_at, RequestDraft.id).where(
                    RequestDraft.requester_id == requester.id
                ),
                RequestDraft.updated_at,
                RequestDraft.id,
                depth,
            ),
            work_cursor=await _cursor_at(
                session,
                select(WorkflowTask.updated_at, WorkflowTask.id),
                WorkflowTask.updated_at,
                WorkflowTask.id,
                depth,
            ),
            user_cursor=await _cursor_at(
                session,
                select(User.updated_at, User.id),
                User.updated_at,
                User.id,
                min(depth, 150),
            ),
            board_cursor=await _board_cursor_at(session, osg_team_id, depth),
            history_cursor=await _cursor_at(
                session,
                select(RequestEvent.created_at, RequestEvent.id).where(
                    RequestEvent.request_id == request_id
                ),
                RequestEvent.created_at,
                RequestEvent.id,
                depth,
            ),
        )


async def _cursor_at(
    session: AsyncSession,
    statement: Select[Any],
    changed_column: Any,
    id_column: Any,
    depth: int,
) -> str:
    row = (
        await session.execute(
            statement.order_by(changed_column.desc(), id_column.desc())
            .offset(depth)
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        raise RuntimeError(f"the fixture does not contain a row at depth {depth}")
    return encode_cursor(row[0], row[1])


async def _board_cursor_at(session: AsyncSession, team_id: UUID, depth: int) -> str:
    row = (
        await session.execute(
            select(WorkPackage.updated_at, WorkPackage.id)
            .where(WorkPackage.team_id == team_id)
            .order_by(WorkPackage.updated_at.desc(), WorkPackage.id.desc())
            .offset(depth)
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        raise RuntimeError(f"the Board fixture has no row at depth {depth}")
    value = f"{_iso(row[0])}|{BoardItemType.WORK_PACKAGE.value}|{row[1]}"
    return urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _iso(value: datetime) -> str:
    return value.isoformat()


async def statement_count_evidence(
    sessions: SessionFactory,
    engine: AsyncEngine,
    context: ScaleContext,
) -> dict[str, Any]:
    board_filters = BoardFilters(item_types=[BoardItemType.WORK_PACKAGE])

    def request_page(cursor: str | None) -> MeasuredCall:
        async def call(session: AsyncSession) -> object:
            return await SqlAlchemyRequestRepository(
                session, process_id="service-request-v1"
            ).page_for_requester(context.requester_id, limit=50, cursor=cursor)

        return call

    def draft_page(cursor: str | None) -> MeasuredCall:
        async def call(session: AsyncSession) -> object:
            return await SqlAlchemyDraftRepository(
                session, process_id="service-request-v1"
            ).page_for_requester(context.requester_id, limit=50, cursor=cursor)

        return call

    def work_page(cursor: str | None) -> MeasuredCall:
        async def call(session: AsyncSession) -> object:
            return await SqlAlchemyWorkRepository(session).page_for_actor(
                context.triage_actor, limit=50, cursor=cursor
            )

        return call

    def admin_page(cursor: str | None) -> MeasuredCall:
        async def call(session: AsyncSession) -> object:
            return await SqlAlchemyAdminRepository(session).page_users(
                None, limit=50, cursor=cursor
            )

        return call

    def tracking_page(cursor: str | None) -> MeasuredCall:
        async def call(session: AsyncSession) -> object:
            repository = SqlAlchemyOrganisationRepository(session)
            return await repository.page_tracked_requests(
                context.triage_actor,
                limit=50,
                cursor=cursor,
            )

        return call

    def board_page(cursor: str | None) -> MeasuredCall:
        async def call(session: AsyncSession) -> object:
            return await SqlAlchemyBoardRepository(session).board_page(
                context.osg_team_id, board_filters, cursor, 50
            )

        return call

    def history_page(cursor: str | None) -> MeasuredCall:
        async def call(session: AsyncSession) -> object:
            return await SqlAlchemyRequestRepository(
                session, process_id="service-request-v1"
            ).get_detail(
                context.request_id,
                reveal_unreleased_deliverable=False,
                event_limit=50,
                event_cursor=cursor,
            )

        return call

    feeds = {
        "requests": (request_page(None), request_page(context.request_cursor)),
        "drafts": (draft_page(None), draft_page(context.draft_cursor)),
        "work": (work_page(None), work_page(context.work_cursor)),
        "tracking": (tracking_page(None), tracking_page(context.request_cursor)),
        "administration": (admin_page(None), admin_page(context.user_cursor)),
        "board": (board_page(None), board_page(context.board_cursor)),
        "history": (history_page(None), history_page(context.history_cursor)),
    }
    counter = StatementCounter(engine)
    try:
        results: dict[str, Any] = {}
        for name, (first, deep) in feeds.items():
            first_result = await _measure(sessions, counter, first)
            deep_result = await _measure(sessions, counter, deep)
            results[name] = {
                "first_page": first_result,
                "deep_page": deep_result,
                "bounded": deep_result["statement_count"]
                <= first_result["statement_count"],
            }
        return results
    finally:
        counter.close()


async def _measure(
    sessions: SessionFactory,
    counter: StatementCounter,
    callback: MeasuredCall,
) -> dict[str, Any]:
    async with sessions() as session:
        counter.start()
        started = perf_counter()
        result = await callback(session)
        elapsed_ms = round((perf_counter() - started) * 1_000, 3)
        statements = counter.stop()
    item_count = len(result[0]) if isinstance(result, tuple) else 1
    return {
        "elapsed_ms": elapsed_ms,
        "item_count": item_count,
        "statement_count": len(statements),
        "statement_types": statements,
    }


async def contention_evidence(sessions: SessionFactory) -> dict[str, Any]:
    started = asyncio.Event()
    release = asyncio.Event()
    callback_count = 0

    async def callback() -> bool:
        nonlocal callback_count
        callback_count += 1
        started.set()
        await release.wait()
        return True

    job = MaintenanceJob("scale-evidence-contention", callback)
    first = WorkerIteration(sessions, (job,), lease_seconds=5, owner="evidence-a")
    second = WorkerIteration(sessions, (job,), lease_seconds=5, owner="evidence-b")
    running = asyncio.create_task(first.run_once())
    await asyncio.wait_for(started.wait(), timeout=5)
    second_worked = await second.run_once()
    release.set()
    first_worked = await running
    return {
        "callback_count": callback_count,
        "first_worker_reported_work": first_worked,
        "second_worker_reported_work": second_worked,
        "passed": callback_count == 1 and first_worked and not second_worked,
    }
