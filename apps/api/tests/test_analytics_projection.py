"""Content-free operational projection behaviour over a complete workflow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_helpers import perform, reach_delivery_work
from conftest import ApiHarness
from istari_service.analytics_models import (
    AnalyticsProjectionState,
    ProjectionHealth,
    RequestAnalyticsFact,
    RequestStageInterval,
)
from istari_service.analytics_projection import (
    PROJECTION_NAME,
    project_request_analytics,
    rebuild_analytics_projections,
)
from istari_service.clarification_models import ClarificationThread
from istari_service.models import RequestStatus, ServiceRequest


async def test_projection_is_idempotent_scoped_and_content_free(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    await perform(
        harness,
        "admin11",
        {
            "action": "request_clarification",
            "question": "Which fictional region should be prioritised?",
            "reason": "The answer is required to complete the product accurately.",
            "responseDeadline": (
                datetime.now(UTC).date() + timedelta(days=5)
            ).isoformat(),
        },
    )
    async with harness.sessions() as session:
        thread = await session.scalar(
            select(ClarificationThread).where(
                ClarificationThread.request_id == UUID(request_id)
            )
        )
        assert thread is not None
        thread_id, thread_version = thread.id, thread.version
    await perform(
        harness,
        "admin2",
        {
            "action": "provide_clarification",
            "threadId": str(thread_id),
            "expectedVersion": thread_version,
            "information": "Prioritise the fictional northern region.",
        },
    )
    await perform(
        harness,
        "admin11",
        {
            "action": "submit",
            "deliverableTitle": "Synthetic first product",
            "deliverableText": "A complete fictional product requiring one revision.",
        },
    )
    await perform(
        harness,
        "admin8",
        {"action": "changes_required", "reason": "Add a clearer conclusion."},
    )
    await perform(
        harness,
        "admin11",
        {
            "action": "submit",
            "deliverableTitle": "Synthetic revised product",
            "deliverableText": (
                "A complete revised fictional product with a conclusion."
            ),
        },
    )
    await perform(harness, "admin8", {"action": "approve"})
    await perform(harness, "admin15", {"action": "approve"})
    await perform(
        harness,
        "admin100",
        {"action": "release", "recipients": ["Fictional service owner"]},
    )
    await harness.login("admin2")
    feedback = await harness.client.post(
        f"/api/v1/requests/{request_id}/feedback",
        json={"rating": 5, "comments": "Clear and useful synthetic service."},
        headers=harness.mutation_headers(),
    )
    assert feedback.status_code == 200
    jock_id = await harness.unit_id("JOCK")
    ncgi_id = await harness.unit_id("ACSA_B_OPS")
    ssg_id = await harness.unit_id("SSG_TEAM")

    async with harness.sessions() as session, session.begin():
        first = await project_request_analytics(session, UUID(request_id))
        initial_rows = await _interval_rows(session, UUID(request_id))
        second = await project_request_analytics(session, UUID(request_id))
        repeated_rows = await _interval_rows(session, UUID(request_id))
        assert first.request_id == second.request_id
        assert initial_rows == repeated_rows
        assert second.current_status is RequestStatus.COMPLETED
        assert second.clarification_count == 1
        assert second.rework_count == 1
        assert (second.feedback_received, second.feedback_rating) == (True, 5)
        assert second.released_at is not None
        assert second.command_unit_id == jock_id
        assert second.ops_unit_id == ncgi_id
        assert second.team_unit_id == ssg_id
        stage_units = {status: unit_id for _sequence, status, unit_id in repeated_rows}
        assert stage_units[RequestStatus.COORDINATION_REVIEW] == second.command_unit_id
        assert stage_units[RequestStatus.ALLOCATION_REVIEW] == second.ops_unit_id
        assert stage_units[RequestStatus.IN_PROGRESS] == second.team_unit_id

        assert await rebuild_analytics_projections(session) == 1
        state = await session.get(AnalyticsProjectionState, PROJECTION_NAME)
        assert state is not None
        assert (state.health, state.projected_request_count) == (
            ProjectionHealth.READY,
            1,
        )
        assert _analytics_columns().isdisjoint(
            {
                "title",
                "description",
                "requester_id",
                "comments",
                "deliverable_text",
                "question",
                "reason",
            }
        )
        request = await session.get(ServiceRequest, UUID(request_id))
        assert request is not None
        assert state.source_event_count == request.audit_event_count


def _analytics_columns() -> set[str]:
    return {
        column.name
        for table in (
            RequestAnalyticsFact.__table__,
            RequestStageInterval.__table__,
        )
        for column in table.columns
    }


async def _interval_rows(
    session: AsyncSession,
    request_id: UUID,
) -> list[tuple[int, RequestStatus, UUID]]:
    rows = await session.execute(
        select(
            RequestStageInterval.sequence,
            RequestStageInterval.status,
            RequestStageInterval.unit_id,
        )
        .where(RequestStageInterval.request_id == request_id)
        .order_by(RequestStageInterval.sequence)
    )
    return list(rows.tuples())
