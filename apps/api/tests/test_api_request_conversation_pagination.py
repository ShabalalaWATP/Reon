"""Bounded conversation pagination and admission-control behaviour."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import postgresql, sqlite

from api_helpers import reach_delivery_work
from conftest import ApiHarness
from istari_service.repositories.conversation_pages import bounded_message_query
from istari_service.services import conversation_limits


def test_bounded_message_window_compiles_for_supported_databases() -> None:
    query = bounded_message_query([uuid4(), uuid4()], limit=50)
    for dialect in (sqlite.dialect(), postgresql.dialect()):
        compiled = str(query.compile(dialect=dialect)).upper()
        assert "ROW_NUMBER() OVER" in compiled
        assert "PARTITION BY" in compiled


async def test_conversation_and_message_pages_use_opaque_bounded_cursors(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    await harness.login("admin11")
    created: list[dict] = []
    for subject in ("First customer question", "Second customer question"):
        response = await harness.client.post(
            f"/api/v1/requests/{request_id}/conversations/messages",
            json={
                "body": f"Synthetic body for {subject.lower()}.",
                "clientMutationId": str(uuid4()),
                "subject": subject,
                "targetType": "CUSTOMER",
            },
            headers=harness.mutation_headers(),
        )
        assert response.status_code == 200, response.text
        created.append(response.json()["conversation"])

    first_page = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations?limit=1&messageLimit=1"
    )
    assert first_page.status_code == 200
    first_cursor = first_page.json()["conversationsNextCursor"]
    assert first_cursor
    second_page = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations",
        params={"limit": 1, "cursor": first_cursor, "messageLimit": 1},
    )
    assert second_page.status_code == 200
    assert (
        second_page.json()["conversations"][0]["id"]
        != (first_page.json()["conversations"][0]["id"])
    )

    conversation = created[0]
    reply = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A second message for bounded history retrieval.",
            "clientMutationId": str(uuid4()),
            "conversationId": conversation["id"],
            "replyToMessageId": conversation["messages"][0]["id"],
        },
        headers=harness.mutation_headers(),
    )
    assert reply.status_code == 200, reply.text
    message_page = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations/{conversation['id']}?limit=1"
    )
    assert message_page.status_code == 200
    message_cursor = message_page.json()["messagesNextCursor"]
    assert message_cursor
    older_page = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations/{conversation['id']}",
        params={"limit": 1, "cursor": message_cursor},
    )
    assert older_page.status_code == 200
    assert (
        older_page.json()["messages"][0]["id"]
        != (message_page.json()["messages"][0]["id"])
    )


async def test_workspace_message_queries_are_constant_for_page_size(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    await harness.login("admin11")
    for number in range(2):
        response = await harness.client.post(
            f"/api/v1/requests/{request_id}/conversations/messages",
            json={
                "body": f"Synthetic bounded query message number {number}.",
                "clientMutationId": str(uuid4()),
                "subject": f"Bounded query thread {number}",
                "targetType": "CUSTOMER",
            },
            headers=harness.mutation_headers(),
        )
        assert response.status_code == 200, response.text

    engine = harness.sessions.kw["bind"]
    statements: list[str] = []

    def capture_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
    try:
        one = await harness.client.get(
            f"/api/v1/requests/{request_id}/conversations",
            params={"limit": 1, "messageLimit": 1},
        )
        one_count = len(statements)
        statements.clear()
        two = await harness.client.get(
            f"/api/v1/requests/{request_id}/conversations",
            params={"limit": 2, "messageLimit": 1},
        )
        two_count = len(statements)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)

    assert one.status_code == 200
    assert two.status_code == 200
    assert len(one.json()["conversations"]) == 1
    assert len(two.json()["conversations"]) == 2
    assert two_count == one_count


async def test_unread_total_is_independent_of_message_page_size(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    await harness.login("admin11")
    opened = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "The first unread synthetic customer message.",
            "clientMutationId": str(uuid4()),
            "subject": "Unread total boundary",
            "targetType": "CUSTOMER",
        },
        headers=harness.mutation_headers(),
    )
    assert opened.status_code == 200, opened.text
    conversation = opened.json()["conversation"]
    reply = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "The second unread synthetic customer message.",
            "clientMutationId": str(uuid4()),
            "conversationId": conversation["id"],
            "replyToMessageId": conversation["messages"][0]["id"],
        },
        headers=harness.mutation_headers(),
    )
    assert reply.status_code == 200, reply.text

    await harness.login("admin2")
    page = await harness.client.get(
        f"/api/v1/requests/{request_id}/conversations/{conversation['id']}",
        params={"limit": 1},
    )
    assert page.status_code == 200, page.text
    assert len(page.json()["messages"]) == 1
    assert page.json()["unreadCount"] == 2


async def test_conversation_admission_limits_are_enforced_atomically(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    await harness.login("admin11")
    monkeypatch.setattr(conversation_limits, "CONVERSATIONS_PER_REQUEST", 1)
    first = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "The sole admitted synthetic conversation.",
            "clientMutationId": str(uuid4()),
            "targetType": "CUSTOMER",
        },
        headers=harness.mutation_headers(),
    )
    assert first.status_code == 200, first.text
    rejected = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A second conversation must exceed the quota.",
            "clientMutationId": str(uuid4()),
            "targetType": "CUSTOMER",
        },
        headers=harness.mutation_headers(),
    )
    assert rejected.status_code == 409

    monkeypatch.setattr(conversation_limits, "CONVERSATIONS_PER_REQUEST", 100)
    monkeypatch.setattr(conversation_limits, "MESSAGES_PER_AUTHOR_PER_REQUEST", 1)
    author_rejected = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "The same author must not exceed their request quota.",
            "clientMutationId": str(uuid4()),
            "conversationId": first.json()["conversation"]["id"],
        },
        headers=harness.mutation_headers(),
    )
    assert author_rejected.status_code == 409

    monkeypatch.setattr(conversation_limits, "MESSAGES_PER_AUTHOR_PER_REQUEST", 500)
    monkeypatch.setattr(conversation_limits, "MESSAGES_PER_REQUEST", 1)
    await harness.login("admin2")
    request_rejected = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "A different author still cannot exceed the request quota.",
            "clientMutationId": str(uuid4()),
            "conversationId": first.json()["conversation"]["id"],
        },
        headers=harness.mutation_headers(),
    )
    assert request_rejected.status_code == 409
