"""Accountable Lead and Contributor history invariants."""

from __future__ import annotations

from sqlalchemy import select

from conftest import ApiHarness, request_payload
from istari_service.models import RequestStatus, ServiceRequest
from istari_service.repositories.request_participants import (
    active_participant_ids,
    replace_request_participants,
)
from istari_service.request_participant_models import (
    RequestParticipant,
    RequestParticipantRole,
)
from istari_service.schemas.requests import RequestCreate


async def test_reassignment_preserves_history_and_one_active_lead(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    requester_id = await harness.user_id("admin2")
    manager_id = await harness.user_id("admin8")
    first_lead = await harness.user_id("admin11")
    contributor = await harness.user_id("admin12")
    next_lead = await harness.user_id("admin13")
    async with harness.sessions() as session, session.begin():
        request = ServiceRequest(
            reference="SR-PARTICIPANT-HISTORY-001",
            requester_id=requester_id,
            status=RequestStatus.IN_PROGRESS,
            current_owner="SSG Team",
            assigned_delivery_team="SSG Team",
            **RequestCreate.model_validate(request_payload()).model_dump(),
        )
        session.add(request)
        await session.flush()
        await replace_request_participants(
            session,
            request_id=request.id,
            lead_id=first_lead,
            contributor_ids=[contributor],
            actor_id=manager_id,
            reason="The initial Lead and Contributor were selected for delivery.",
        )
        await replace_request_participants(
            session,
            request_id=request.id,
            lead_id=next_lead,
            contributor_ids=[first_lead],
            actor_id=manager_id,
            reason=(
                "Accountability moved while preserving the earlier assignment history."
            ),
        )
        assert await active_participant_ids(session, request.id) == {
            next_lead,
            first_lead,
        }
        rows = list(
            await session.scalars(
                select(RequestParticipant)
                .where(RequestParticipant.request_id == request.id)
                .order_by(RequestParticipant.created_at, RequestParticipant.id)
            )
        )
        active = [item for item in rows if item.ended_at is None]
        assert len(rows) == 4
        assert [item.role for item in active].count(RequestParticipantRole.LEAD) == 1
        assert (
            next(
                item for item in active if item.role is RequestParticipantRole.LEAD
            ).user_id
            == next_lead
        )
        assert all(item.end_reason for item in rows if item.ended_at is not None)
