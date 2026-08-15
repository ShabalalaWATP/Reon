"""Exact live-QC-membership boundaries for structured conversations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update

from api_helpers import reach_delivery_work
from conftest import ApiHarness
from mist_service.conversation_models import RequestConversationDelivery
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.qc_membership import QC_TEAM_ID
from mist_service.team_models import TeamMembership


async def _expire_qc_membership(harness: ApiHarness, user_id: UUID) -> None:
    async with harness.sessions() as session, session.begin():
        await session.execute(
            update(TeamMembership)
            .where(
                TeamMembership.user_id == user_id,
                TeamMembership.team_id == QC_TEAM_ID,
                TeamMembership.effective_until.is_(None),
            )
            .values(effective_until=datetime.now(UTC))
        )


async def test_expired_qc_membership_loses_thread_and_recipient_access(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    qc_reviewer_id = await harness.user_id("admin15")
    qc_releaser_id = await harness.user_id("admin100")
    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, UUID(request_id))
        assert request is not None
        request.status = RequestStatus.QUALITY_REVIEW
        request.current_owner = "QC Team"

    await harness.login("admin15")
    created = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A synthetic question for the combined QC team.",
            "clientMutationId": str(uuid4()),
            "targetType": "QC_TEAM",
        },
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 200, created.text
    conversation_id = created.json()["conversation"]["id"]
    first_message_id = created.json()["conversation"]["messages"][0]["id"]
    async with harness.sessions() as session:
        initial_delivery = await session.scalar(
            select(RequestConversationDelivery).where(
                RequestConversationDelivery.message_id == UUID(first_message_id),
                RequestConversationDelivery.recipient_user_id == qc_releaser_id,
            )
        )
        assert initial_delivery is not None

    await _expire_qc_membership(harness, qc_releaser_id)
    reply = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "Expired QC members must not enter the delivery snapshot.",
            "clientMutationId": str(uuid4()),
            "conversationId": conversation_id,
            "replyToMessageId": first_message_id,
        },
        headers=harness.mutation_headers(),
    )
    assert reply.status_code == 200, reply.text
    reply_message = next(
        message
        for message in reply.json()["conversation"]["messages"]
        if message["replyToMessageId"] is not None
    )
    async with harness.sessions() as session:
        expired_delivery = await session.scalar(
            select(RequestConversationDelivery).where(
                RequestConversationDelivery.message_id == UUID(reply_message["id"]),
                RequestConversationDelivery.recipient_user_id == qc_releaser_id,
            )
        )
        assert expired_delivery is None

    await _expire_qc_membership(harness, qc_reviewer_id)
    denied_list = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations"
    )
    assert denied_list.status_code == 404
    denied_detail = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations/{conversation_id}"
    )
    assert denied_detail.status_code == 404
    denied_reply = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "Role alone must not preserve QC conversation access.",
            "clientMutationId": str(uuid4()),
            "conversationId": conversation_id,
        },
        headers=harness.mutation_headers(),
    )
    assert denied_reply.status_code == 404
