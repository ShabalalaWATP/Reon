"""Conversation destinations, replies and lifecycle recipient behaviour."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from api_helpers import reach_delivery_work
from conftest import ApiHarness
from mist_service.conversation_models import (
    RequestConversationDelivery,
    RequestConversationMessage,
)
from mist_service.models import RequestStatus, ServiceRequest
from mist_service.request_participant_models import (
    RequestParticipant,
    RequestParticipantRole,
)


async def _set_status(
    harness: ApiHarness,
    request_id: str,
    status: RequestStatus,
    owner: str,
) -> None:
    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, UUID(request_id))
        assert request is not None
        request.status = status
        request.current_owner = owner


async def _post_target(harness: ApiHarness, request_id: str, target: dict) -> dict:
    response = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A recorded synthetic coordination message.",
            "clientMutationId": str(uuid4()),
            **target,
        },
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_assigned_analyst_replies_read_state_and_lifecycle_targets(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    ben_id = await harness.user_id("admin13")
    manager_id = await harness.user_id("admin8")
    async with harness.sessions() as session, session.begin():
        session.add(
            RequestParticipant(
                request_id=UUID(request_id),
                user_id=ben_id,
                role=RequestParticipantRole.CONTRIBUTOR,
                assigned_by_user_id=manager_id,
                reason="Ben is contributing to the synthetic product.",
                effective_from=datetime.now(UTC),
            )
        )

    await harness.login("admin13")
    workspace = await harness.client.get(f"/api/v1/requests/{request_id}/conversations")
    assert workspace.status_code == 200
    crioc_target = next(
        target
        for target in workspace.json()["allowedTargets"]
        if target["type"] == "ROUTE_UNIT" and target["label"] == "JIOC"
    )
    assigned = await _post_target(
        harness, request_id, {"targetType": "ASSIGNED_ANALYSTS"}
    )
    assigned_conversation_id = assigned["conversation"]["id"]
    for target in (
        {"targetType": "ROUTE_UNIT", "targetUnitId": crioc_target["unitId"]},
        {"targetType": "CURRENT_OWNER"},
    ):
        await _post_target(harness, request_id, target)
    created = await _post_target(harness, request_id, {"targetType": "TEAM_MANAGERS"})
    conversation_id = created["conversation"]["id"]
    message_id = created["conversation"]["messages"][0]["id"]

    await harness.login("admin8")
    manager_workspace = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations"
    )
    manager_thread = next(
        item
        for item in manager_workspace.json()["conversations"]
        if item["id"] == conversation_id
    )
    assert manager_thread["unreadCount"] == 1
    for payload in (
        {"conversationId": conversation_id, "replyToMessageId": str(uuid4())},
        {"conversationId": str(uuid4())},
    ):
        response = await harness.client.post(
            f"/api/v1/requests/{request_id}/conversations/messages",
            json={
                "body": "This invalid reply must fail without disclosure.",
                "clientMutationId": str(uuid4()),
                **payload,
            },
            headers=harness.mutation_headers(),
        )
        assert response.status_code == 404
    reply = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "Use a short confidence note beside each principal judgement.",
            "clientMutationId": str(uuid4()),
            "conversationId": conversation_id,
            "replyToMessageId": message_id,
        },
        headers=harness.mutation_headers(),
    )
    assert reply.status_code == 200
    assert len(reply.json()["conversation"]["messages"]) == 2
    reply_message = next(
        message
        for message in reply.json()["conversation"]["messages"]
        if message["replyToMessageId"] is not None
    )
    nested_reply = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A nested reply must be rejected by the server.",
            "clientMutationId": str(uuid4()),
            "conversationId": conversation_id,
            "replyToMessageId": reply_message["id"],
        },
        headers=harness.mutation_headers(),
    )
    assert nested_reply.status_code == 409
    marked = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/{conversation_id}/read",
        headers=harness.mutation_headers(),
    )
    assert marked.status_code == 200
    async with harness.sessions() as session:
        message = await session.scalar(
            select(RequestConversationMessage).where(
                RequestConversationMessage.conversation_id == UUID(conversation_id)
            )
        )
        assert message is not None
        message.body = "Attempted mutation of immutable content."
        with pytest.raises(ValueError, match="append-only"):
            await session.flush()
        await session.rollback()
    async with harness.sessions() as session:
        delivery = await session.scalar(
            select(RequestConversationDelivery)
            .join(
                RequestConversationMessage,
                RequestConversationMessage.id == RequestConversationDelivery.message_id,
            )
            .where(
                RequestConversationMessage.conversation_id == UUID(conversation_id),
                RequestConversationDelivery.recipient_user_id == manager_id,
            )
        )
        assert delivery is not None and delivery.read_at is not None
        delivery.read_at = None
        with pytest.raises(ValueError, match="can only advance once"):
            await session.flush()
        await session.rollback()
    missing_read = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/{uuid4()}/read",
        headers=harness.mutation_headers(),
    )
    assert missing_read.status_code == 404

    # Being the opener is not an enduring authorisation grant. Once removed from
    # the live assignment, Ben cannot list, directly address or reply to the thread.
    async with harness.sessions() as session, session.begin():
        await session.execute(
            update(RequestParticipant)
            .where(
                RequestParticipant.request_id == UUID(request_id),
                RequestParticipant.user_id == ben_id,
            )
            .values(ended_at=datetime.now(UTC))
        )
    await harness.login("admin13")
    removed_workspace = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations"
    )
    assert removed_workspace.status_code == 200
    assert assigned_conversation_id not in {
        item["id"] for item in removed_workspace.json()["conversations"]
    }
    removed_detail = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations/{assigned_conversation_id}"
    )
    assert removed_detail.status_code == 404
    removed_reply = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A removed analyst must not retain access through authorship.",
            "clientMutationId": str(uuid4()),
            "conversationId": assigned_conversation_id,
        },
        headers=harness.mutation_headers(),
    )
    assert removed_reply.status_code == 404
    await harness.login("admin8")

    await _set_status(
        harness, request_id, RequestStatus.DELIVERY_PLANNING, "OSG Team Managers"
    )
    await _post_target(harness, request_id, {"targetType": "CURRENT_OWNER"})
    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, UUID(request_id))
        assert request is not None
        request.assigned_specialist_id = None
    await _post_target(harness, request_id, {"targetType": "ASSIGNED_ANALYSTS"})

    await _set_status(harness, request_id, RequestStatus.QUALITY_REVIEW, "QC Team")
    await harness.login("admin15")
    qc_workspace = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations"
    )
    assert qc_workspace.status_code == 200
    assert "QC_TEAM" in {
        target["type"] for target in qc_workspace.json()["allowedTargets"]
    }
    for target_type in ("QC_TEAM", "CURRENT_OWNER"):
        await _post_target(harness, request_id, {"targetType": target_type})

    await _set_status(harness, request_id, RequestStatus.TRIAGE_REVIEW, "JIOC Routing")
    await harness.login("admin4")
    await _post_target(harness, request_id, {"targetType": "CURRENT_OWNER"})

    await _set_status(harness, request_id, RequestStatus.COMPLETED, "Customer")
    await harness.login("admin2")
    await _post_target(harness, request_id, {"targetType": "CURRENT_OWNER"})

    # A stale named-Analyst pointer is not a live conversation recipient.
    analyst_id = await harness.user_id("admin11")
    async with harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, UUID(request_id))
        assert request is not None
        request.status = RequestStatus.IN_PROGRESS
        request.current_owner = "Team Analyst"
        request.assigned_specialist_id = analyst_id
        await session.execute(
            update(RequestParticipant)
            .where(RequestParticipant.request_id == UUID(request_id))
            .values(ended_at=datetime.now(UTC))
        )
    await harness.login("admin11")
    stale_target = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A stale assignment must not receive conversation content.",
            "clientMutationId": str(uuid4()),
            "targetType": "CURRENT_OWNER",
        },
        headers=harness.mutation_headers(),
    )
    assert stale_target.status_code == 409

    await _set_status(harness, request_id, RequestStatus.CANCELLED, "No current owner")
    await harness.login("admin4")
    no_owner = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A cancelled request has no current conversation recipient.",
            "clientMutationId": str(uuid4()),
            "targetType": "CURRENT_OWNER",
        },
        headers=harness.mutation_headers(),
    )
    assert no_owner.status_code == 409
