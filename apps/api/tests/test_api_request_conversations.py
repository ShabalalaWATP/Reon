"""Structured request-conversation API security and history behaviour."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select

from api_helpers import reach_delivery_work
from conftest import ApiHarness, request_payload
from istari_service.conversation_models import RequestConversationMessage
from istari_service.repositories.event_store import verify_request_event_integrity
from istari_service.request_event_models import RequestEvent
from istari_service.schemas.conversations import ConversationMessageCreate


@pytest.mark.parametrize(
    "payload",
    [
        {"body": "Missing target", "clientMutationId": uuid4()},
        {
            "body": "New thread with reply",
            "clientMutationId": uuid4(),
            "targetType": "CUSTOMER",
            "replyToMessageId": uuid4(),
        },
        {
            "body": "Missing route unit",
            "clientMutationId": uuid4(),
            "targetType": "ROUTE_UNIT",
        },
        {
            "body": "Unexpected route unit",
            "clientMutationId": uuid4(),
            "targetType": "CUSTOMER",
            "targetUnitId": uuid4(),
        },
        {
            "body": "Reply changing target",
            "clientMutationId": uuid4(),
            "conversationId": uuid4(),
            "targetType": "CUSTOMER",
        },
    ],
)
def test_conversation_commands_reject_ambiguous_shapes(payload: dict) -> None:
    with pytest.raises(ValidationError):
        ConversationMessageCreate.model_validate(payload)


def test_conversation_command_normalises_body_and_subject() -> None:
    command = ConversationMessageCreate(
        body="  A   bounded message body. ",
        subject="  A   clear subject. ",
        clientMutationId=uuid4(),
        targetType="CUSTOMER",
    )
    assert command.body == "A bounded message body."
    assert command.subject == "A clear subject."


async def test_staff_context_cannot_coordinate_its_own_customer_request(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin11")
    switched = await harness.client.post(
        "/api/v1/auth/switch-context",
        json={"context": "CUSTOMER"},
        headers=harness.mutation_headers(),
    )
    assert switched.status_code == 200, switched.text
    harness.csrf_token = switched.json()["csrfToken"]
    created = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(),
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 201, created.text
    switched = await harness.client.post(
        "/api/v1/auth/switch-context",
        json={"context": "STAFF"},
        headers=harness.mutation_headers(),
    )
    assert switched.status_code == 200, switched.text
    harness.csrf_token = switched.json()["csrfToken"]
    denied = await harness.client.get(
        f"/api/v1/requests/{created.json()['id']}/conversations"
    )
    assert denied.status_code == 404


async def test_customer_context_cannot_reuse_staff_assignment_on_another_request(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    await harness.login("admin11")
    created = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A staff message that must remain outside Ben's Customer context.",
            "clientMutationId": str(uuid4()),
            "targetType": "CUSTOMER",
        },
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 200, created.text
    conversation_id = created.json()["conversation"]["id"]
    switched = await harness.client.post(
        "/api/v1/auth/switch-context",
        json={"context": "CUSTOMER"},
        headers=harness.mutation_headers(),
    )
    assert switched.status_code == 200, switched.text
    harness.csrf_token = switched.json()["csrfToken"]

    assert (
        await harness.client.get(f"/api/v1/requests/{request_id}/conversations")
    ).status_code == 404
    statements: list[str] = []
    engine = harness.sessions.kw["bind"]

    def capture_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement.lower())

    event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
    try:
        denied_detail = await harness.client.get(
            f"/api/v1/requests/{request_id}/conversations/{conversation_id}"
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)
    assert denied_detail.status_code == 404
    assert not any("request_conversation_messages" in sql for sql in statements)
    denied_post = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "Customer context cannot use the underlying staff assignment.",
            "clientMutationId": str(uuid4()),
            "targetType": "CURRENT_OWNER",
        },
        headers=harness.mutation_headers(),
    )
    assert denied_post.status_code == 404
    denied_read = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/{conversation_id}/read",
        headers=harness.mutation_headers(),
    )
    assert denied_read.status_code == 404


async def test_conversations_are_idempotent_scoped_and_customer_safe(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    await harness.login("admin11")

    workspace = await harness.client.get(f"/api/v1/requests/{request_id}/conversations")
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["conversations"] == []
    targets = workspace.json()["allowedTargets"]
    assert {target["type"] for target in targets} == {
        "CUSTOMER",
        "CURRENT_OWNER",
        "TEAM_MANAGERS",
        "ASSIGNED_ANALYSTS",
        "ROUTE_UNIT",
    }
    route_labels = {
        target["label"] for target in targets if target["type"] == "ROUTE_UNIT"
    }
    assert route_labels == {"CRIOC", "JOCK", "ACSA-B Ops"}

    forged = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "This arbitrary unit must not be addressable.",
            "clientMutationId": str(uuid4()),
            "targetType": "ROUTE_UNIT",
            "targetUnitId": str(uuid4()),
        },
        headers=harness.mutation_headers(),
    )
    assert forged.status_code == 404

    mutation_id = uuid4()
    command = {
        "body": "Can the Customer confirm the required presentation format?",
        "clientMutationId": str(mutation_id),
        "subject": "Presentation format",
        "targetType": "CUSTOMER",
    }
    created = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json=command,
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 200, created.text
    repeated = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json=command,
        headers=harness.mutation_headers(),
    )
    assert repeated.status_code == 200
    assert repeated.json()["conversation"] == created.json()["conversation"]
    assert repeated.json()["event"]["id"] == created.json()["event"]["id"]
    conflict = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={**command, "body": "The reused key cannot alter the message."},
        headers=harness.mutation_headers(),
    )
    assert conflict.status_code == 409

    internal = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "Can the SSG Managers confirm the review approach?",
            "clientMutationId": str(uuid4()),
            "targetType": "TEAM_MANAGERS",
        },
        headers=harness.mutation_headers(),
    )
    assert internal.status_code == 200, internal.text
    assert internal.json()["conversation"]["visibility"] == "STAFF_ONLY"

    await harness.login("admin2")
    customer_view = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations"
    )
    assert customer_view.status_code == 200
    assert [item["subject"] for item in customer_view.json()["conversations"]] == [
        "Presentation format"
    ]
    assert customer_view.json()["allowedTargets"] == [
        {"type": "CURRENT_OWNER", "unitId": None, "label": "Team Analyst"}
    ]
    customer_reply = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A PDF presentation is preferred for this request.",
            "clientMutationId": str(uuid4()),
            "conversationId": created.json()["conversation"]["id"],
            "replyToMessageId": created.json()["conversation"]["messages"][0]["id"],
        },
        headers=harness.mutation_headers(),
    )
    assert customer_reply.status_code == 200, customer_reply.text
    hidden_reply = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "The Customer cannot enter this internal thread.",
            "clientMutationId": str(uuid4()),
            "conversationId": internal.json()["conversation"]["id"],
        },
        headers=harness.mutation_headers(),
    )
    assert hidden_reply.status_code == 404

    await harness.login("admin22")
    denied = await harness.client.get(f"/api/v1/requests/{request_id}/conversations")
    assert denied.status_code == 404
    await harness.login("admin1")
    admin_denied = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations"
    )
    assert admin_denied.status_code == 404

    async with harness.sessions() as session:
        message_count = await session.scalar(
            select(func.count(RequestConversationMessage.id))
        )
        conversation_events = await session.scalar(
            select(func.count(RequestEvent.id)).where(
                RequestEvent.request_id == UUID(request_id),
                RequestEvent.type == "REQUEST_MESSAGE_POSTED",
            )
        )
        assert message_count == 3
        assert conversation_events == 3
        assert await verify_request_event_integrity(session, UUID(request_id))
