"""Deterministic request, queue, tracking, draft and history scale fixture."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.audit import canonical_anchor_mac, canonical_event_hash
from istari_service.models import (
    RequestEvent,
    RequestStatus,
    ServiceRequest,
    User,
    UserRole,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTask,
    WorkflowTaskStatus,
)
from istari_service.organisation_models import (
    OrganisationUnit,
    RequestRouteSelection,
)
from istari_service.repositories.event_store import audit_key_for_session
from istari_service.request_draft_models import RequestDraft

FIXTURE_NAMESPACE = "https://istari.example/performance/"


def fixture_id(kind: str, sequence: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}{kind}/{sequence}")


async def seed_request_feeds(
    session: AsyncSession,
    target: int,
) -> dict[str, Any]:
    requester_id = await session.scalar(
        select(User.id).where(User.username == "admin2")
    )
    crioc_id = await session.scalar(
        select(OrganisationUnit.id).where(OrganisationUnit.code == "CRIOC")
    )
    if requester_id is None or crioc_id is None:
        raise RuntimeError("admin2 and the CRIOC unit must exist before scale seeding")
    request_ids = [fixture_id("request", sequence) for sequence in range(1, target + 1)]
    added_requests = await _seed_requests(session, requester_id, request_ids)
    added_drafts = await _seed_drafts(session, requester_id, target)
    added_routes = await _seed_routes(session, crioc_id, request_ids)
    added_instances = await _seed_instances(session, request_ids)
    added_tasks = await _seed_tasks(session, request_ids)
    event_count = await _seed_history(session, request_ids[0], requester_id, target)
    counts = {
        "request_feed_count": await _count_ids(session, ServiceRequest.id, request_ids),
        "draft_feed_count": await _count_ids(
            session,
            RequestDraft.id,
            [fixture_id("draft", sequence) for sequence in range(1, target + 1)],
        ),
        "tracking_feed_count": await _count_ids(
            session, RequestRouteSelection.request_id, request_ids
        ),
        "work_feed_count": await _count_ids(
            session,
            WorkflowTask.id,
            [fixture_id("task", sequence) for sequence in range(1, target + 1)],
        ),
        "history_event_count": event_count,
    }
    return {
        **counts,
        "request_rows_added": added_requests,
        "draft_rows_added": added_drafts,
        "route_rows_added": added_routes,
        "workflow_instances_added": added_instances,
        "work_rows_added": added_tasks,
        "history_request_id": str(request_ids[0]),
        "passed": all(value >= target for value in counts.values()),
    }


async def _seed_requests(
    session: AsyncSession, requester_id: UUID, ids: list[UUID]
) -> int:
    existing = await _existing_ids(session, ServiceRequest.id, ids)
    rows = []
    for sequence, request_id in enumerate(ids, start=1):
        if request_id in existing:
            continue
        changed_at = datetime(2026, 8, 1, tzinfo=UTC) + timedelta(seconds=sequence)
        rows.append(
            ServiceRequest(
                id=request_id,
                reference=f"PERF-{sequence:06d}",
                requester_id=requester_id,
                title=f"Performance rehearsal request {sequence:04d}",
                service_category="Synthetic research support",
                description="Synthetic request used for bounded query evidence.",
                question_to_answer="What does the synthetic evidence show?",
                desired_outcome="A bounded authorised projection.",
                background_context="Synthetic performance context only.",
                subject_area_or_location="Synthetic subject area",
                coverage_start=date(2026, 8, 1),
                coverage_end=date(2026, 8, 31),
                customer_urgency="ROUTINE",
                supported_activity_or_decision="A performance rehearsal decision.",
                required_by=date(2026, 9, 1) + timedelta(days=sequence % 28),
                required_by_reason="Synthetic performance rehearsal.",
                preferred_deliverable_type="PDF",
                success_criteria="The scoped page remains bounded.",
                constraints_or_caveats="No known constraints.",
                supporting_information="No supporting material is available.",
                sensitivity="STANDARD",
                handling_instructions="Synthetic data only.",
                status=RequestStatus.TRIAGE_REVIEW,
                current_owner="CRIOC Routing",
                created_at=changed_at,
                updated_at=changed_at,
            )
        )
    session.add_all(rows)
    await session.flush()
    return len(rows)


async def _seed_drafts(session: AsyncSession, requester_id: UUID, target: int) -> int:
    ids = [fixture_id("draft", sequence) for sequence in range(1, target + 1)]
    existing = await _existing_ids(session, RequestDraft.id, ids)
    rows = [
        RequestDraft(
            id=draft_id,
            requester_id=requester_id,
            title=f"Performance rehearsal draft {sequence:04d}",
            created_at=datetime(2026, 8, 1, tzinfo=UTC) + timedelta(seconds=sequence),
            updated_at=datetime(2026, 8, 1, tzinfo=UTC) + timedelta(seconds=sequence),
        )
        for sequence, draft_id in enumerate(ids, start=1)
        if draft_id not in existing
    ]
    session.add_all(rows)
    await session.flush()
    return len(rows)


async def _seed_routes(
    session: AsyncSession, crioc_id: UUID, request_ids: list[UUID]
) -> int:
    existing = await _existing_ids(
        session, RequestRouteSelection.request_id, request_ids
    )
    rows = [
        RequestRouteSelection(request_id=request_id, unit_id=crioc_id, position=0)
        for request_id in request_ids
        if request_id not in existing
    ]
    session.add_all(rows)
    await session.flush()
    return len(rows)


async def _seed_instances(session: AsyncSession, request_ids: list[UUID]) -> int:
    existing = await _existing_ids(session, WorkflowInstance.request_id, request_ids)
    rows = [
        WorkflowInstance(
            id=fixture_id("instance", sequence),
            request_id=request_id,
            process_id="service-request-v1",
            process_instance_key=f"performance-instance-{sequence:06d}",
            status=WorkflowInstanceStatus.ACTIVE,
            current_element_id="triage_review",
            started_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
        for sequence, request_id in enumerate(request_ids, start=1)
        if request_id not in existing
    ]
    session.add_all(rows)
    await session.flush()
    return len(rows)


async def _seed_tasks(session: AsyncSession, request_ids: list[UUID]) -> int:
    ids = [fixture_id("task", sequence) for sequence in range(1, len(request_ids) + 1)]
    existing = await _existing_ids(session, WorkflowTask.id, ids)
    rows = []
    for sequence, (task_id, request_id) in enumerate(
        zip(ids, request_ids, strict=True), start=1
    ):
        if task_id in existing:
            continue
        changed_at = datetime(2026, 8, 1, tzinfo=UTC) + timedelta(seconds=sequence)
        rows.append(
            WorkflowTask(
                id=task_id,
                request_id=request_id,
                workflow_instance_id=fixture_id("instance", sequence),
                task_key=f"performance-task-{sequence:06d}",
                element_id="triage_review",
                name="CRIOC routing review",
                candidate_role=UserRole.INTAKE_TRIAGE,
                expected_status=RequestStatus.TRIAGE_REVIEW,
                status=WorkflowTaskStatus.OPEN,
                created_at=changed_at,
                updated_at=changed_at,
            )
        )
    session.add_all(rows)
    await session.flush()
    return len(rows)


async def _seed_history(
    session: AsyncSession, request_id: UUID, actor_id: UUID, target: int
) -> int:
    count = int(
        await session.scalar(
            select(func.count())
            .select_from(RequestEvent)
            .where(RequestEvent.request_id == request_id)
        )
        or 0
    )
    if count == target:
        return count
    request = await session.get(ServiceRequest, request_id)
    if request is None or count or request.audit_event_count:
        raise RuntimeError("the history performance fixture is partial or contaminated")
    key = audit_key_for_session(session)
    previous_hash: str | None = None
    rows = []
    for sequence in range(1, target + 1):
        created_at = datetime(2026, 8, 1, tzinfo=UTC) + timedelta(microseconds=sequence)
        details = {"fixture": True, "sequence": sequence}
        event_hash = canonical_event_hash(
            request_id=request_id,
            event_type="performance_fixture",
            message="Synthetic performance history event.",
            actor_id=actor_id,
            created_at=created_at,
            previous_hash=previous_hash,
            audit_key=key,
            prior_status=RequestStatus.TRIAGE_REVIEW,
            next_status=RequestStatus.TRIAGE_REVIEW,
            details=details,
        )
        rows.append(
            RequestEvent(
                id=fixture_id("event", sequence),
                request_id=request_id,
                actor_user_id=actor_id,
                type="performance_fixture",
                message="Synthetic performance history event.",
                prior_status=RequestStatus.TRIAGE_REVIEW,
                next_status=RequestStatus.TRIAGE_REVIEW,
                details=details,
                previous_hash=previous_hash,
                event_hash=event_hash,
                created_at=created_at,
            )
        )
        previous_hash = event_hash
    session.add_all(rows)
    request.audit_event_count = target
    request.audit_head_hash = previous_hash
    if previous_hash is None:
        raise RuntimeError("the history fixture did not produce an audit head")
    request.audit_anchor_mac = canonical_anchor_mac(
        request_id=request_id,
        event_count=target,
        head_hash=previous_hash,
        audit_key=key,
    )
    await session.flush()
    return target


async def _existing_ids(
    session: AsyncSession, column: Any, ids: Sequence[UUID]
) -> set[UUID]:
    found: set[UUID] = set()
    for offset in range(0, len(ids), 500):
        found.update(
            await session.scalars(
                select(column).where(column.in_(ids[offset : offset + 500]))
            )
        )
    return found


async def _count_ids(session: AsyncSession, column: Any, ids: Sequence[UUID]) -> int:
    return len(await _existing_ids(session, column, ids))
