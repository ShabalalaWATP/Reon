"""Upgrade and constraint assertions for the PostgreSQL migration round-trip."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from postgres_migration_probe import (
    REVISION_0043,
    REVISION_0044,
    REVISION_0045,
    REVISION_0046,
    REVISION_0047,
    assert_revision,
    must_reject,
    rows,
    scalar,
)
from postgres_migration_seed import (
    CONVERSATION_ID,
    CRIOC_ID,
    DELIVERY_ID,
    LEGACY_REQUEST_ID,
    MANAGED_REQUEST_ID,
    MESSAGE_ID,
    PACKAGE_ID,
    QC_ACTIVE_ID,
    QC_INACTIVE_ID,
    QC_TEAM_ID,
    REQUEST_EVENT_ID,
    REQUESTER_ID,
    SECOND_PACKAGE_ID,
    STAFF_ID,
    seed_manual_qc_history,
    seed_revision_0043,
)


async def assert_0043(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0043)
    await seed_revision_0043(connection)
    await must_reject(
        connection,
        "INSERT INTO security_events (id, event_type, outcome, reason_code, "
        "deduplication_key) VALUES (:id, 'MIGRATION_ASSURANCE', 'DENIED', "
        "'SYNTHETIC', 'roundtrip-key')",
        {"id": UUID("60000000-0000-0000-0000-000000000002")},
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM security_events "
            "WHERE deduplication_key='roundtrip-key'",
        )
        == 1
    )


async def assert_0044(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0044)
    contexts = await rows(
        connection,
        "SELECT username, customer_context_enabled FROM users ORDER BY username",
    )
    assert dict(contexts) == {
        "migration.qc.active": True,
        "migration.qc.inactive": True,
        "migration.requester": False,
        "migration.staff": True,
    }
    sessions = await rows(
        connection,
        "SELECT users.username, sessions.active_context, sessions.context_version "
        "FROM sessions JOIN users ON users.id=sessions.user_id "
        "ORDER BY users.username",
    )
    assert sessions == [
        ("migration.requester", "CUSTOMER", 1),
        ("migration.staff", "STAFF", 1),
    ]
    modes = dict(
        await rows(
            connection,
            "SELECT id::text, product_mode FROM service_requests ORDER BY id",
        )
    )
    assert modes[str(MANAGED_REQUEST_ID)] == "MANAGED"
    assert modes[str(LEGACY_REQUEST_ID)] == "LEGACY"
    assert await rows(
        connection,
        "SELECT code, name, kind, parent_id::text, staffing_status, "
        "manager_candidate_group, analyst_candidate_group, is_configured "
        "FROM organisation_units WHERE id=:team",
        {"team": QC_TEAM_ID},
    ) == [
        (
            "QC_TEAM",
            "Combined QC Team",
            "TEAM",
            str(CRIOC_ID),
            "STAFFED",
            "qc-team-managers",
            "qc-team-members",
            False,
        )
    ]
    await must_reject(
        connection,
        "UPDATE sessions SET active_context='INVALID' WHERE user_id=:user",
        {"user": STAFF_ID},
    )
    await must_reject(
        connection,
        "UPDATE service_requests SET product_mode='INVALID' WHERE id=:request",
        {"request": MANAGED_REQUEST_ID},
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM team_memberships WHERE user_id=:user AND "
            "team_id=:team AND workspace_position='MANAGER' "
            "AND effective_until IS NULL",
            {"user": QC_ACTIVE_ID, "team": QC_TEAM_ID},
        )
        == 1
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM team_memberships "
            "WHERE user_id=:user AND team_id=:team",
            {"user": QC_INACTIVE_ID, "team": QC_TEAM_ID},
        )
        == 0
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM user_organisation_memberships "
            "WHERE user_id=:user AND unit_id=:team",
            {"user": QC_ACTIVE_ID, "team": QC_TEAM_ID},
        )
        == 1
    )
    await seed_manual_qc_history(connection)
    await connection.execute(
        text(
            "UPDATE product_packages SET covering_note='Synthetic covering note' "
            "WHERE id=:id"
        ),
        {"id": PACKAGE_ID},
    )
    await _seed_conversation_evidence(connection)


async def _seed_conversation_evidence(connection: AsyncConnection) -> None:
    await connection.execute(
        text(
            "INSERT INTO request_events (id, request_id, actor_user_id, type, message, "
            "audience, details, event_hash) VALUES (:event, :request, :staff, "
            "'MIGRATION_ASSURANCE', 'Synthetic conversation event', 'STAFF_ONLY', "
            "'{}', :event_hash)"
        ),
        {
            "event": REQUEST_EVENT_ID,
            "request": MANAGED_REQUEST_ID,
            "staff": STAFF_ID,
            "event_hash": "a" * 64,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO request_conversations (id, request_id, opened_by_user_id, "
            "target_type, target_label, subject, visibility) VALUES "
            "(:id, :request, :staff, 'CUSTOMER', 'Customer', "
            "'Synthetic migration conversation', 'CUSTOMER_AND_STAFF')"
        ),
        {"id": CONVERSATION_ID, "request": MANAGED_REQUEST_ID, "staff": STAFF_ID},
    )
    await connection.execute(
        text(
            "INSERT INTO request_conversation_messages (id, conversation_id, "
            "sender_user_id, sender_role, body, body_sha256, client_mutation_id, "
            "request_event_id) VALUES (:id, :conversation, :staff, "
            "'DELIVERY_SPECIALIST', 'Synthetic message', :body_hash, :mutation, :event)"
        ),
        {
            "id": MESSAGE_ID,
            "conversation": CONVERSATION_ID,
            "staff": STAFF_ID,
            "body_hash": "b" * 64,
            "mutation": UUID("50000000-0000-0000-0000-000000000005"),
            "event": REQUEST_EVENT_ID,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO request_conversation_deliveries "
            "(id, message_id, recipient_user_id) VALUES (:id, :message, :recipient)"
        ),
        {"id": DELIVERY_ID, "message": MESSAGE_ID, "recipient": REQUESTER_ID},
    )
    await connection.execute(
        text("UPDATE request_conversation_deliveries SET read_at=now() WHERE id=:id"),
        {"id": DELIVERY_ID},
    )
    await must_reject(
        connection,
        "UPDATE request_conversation_deliveries "
        "SET read_at=now() + INTERVAL '1 second' WHERE id=:id",
        {"id": DELIVERY_ID},
    )
    await must_reject(
        connection,
        "DELETE FROM request_conversation_deliveries WHERE id=:id",
        {"id": DELIVERY_ID},
    )
    await must_reject(
        connection,
        "INSERT INTO request_conversation_deliveries "
        "(id, message_id, recipient_user_id) VALUES (:id, :message, :recipient)",
        {
            "id": UUID("50000000-0000-0000-0000-000000000006"),
            "message": MESSAGE_ID,
            "recipient": REQUESTER_ID,
        },
    )


async def assert_0045(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0045)
    assert (
        await scalar(
            connection,
            "SELECT identity_context FROM notification_preferences WHERE user_id=:user",
            {"user": REQUESTER_ID},
        )
        == "CUSTOMER"
    )
    assert (
        await scalar(
            connection,
            "SELECT identity_context FROM notification_preferences WHERE user_id=:user",
            {"user": STAFF_ID},
        )
        == "STAFF"
    )
    await connection.execute(
        text(
            "INSERT INTO notification_preferences (id, user_id, event_group, "
            "identity_context, enabled, reminder_days) VALUES "
            "(:id, :user, 'REQUEST_LIFECYCLE', 'CUSTOMER', true, '[5]')"
        ),
        {"id": UUID("80000000-0000-0000-0000-000000000003"), "user": STAFF_ID},
    )
    await must_reject(
        connection,
        "INSERT INTO notification_preferences (id, user_id, event_group, "
        "identity_context, enabled, reminder_days) VALUES "
        "(:id, :user, 'REQUEST_LIFECYCLE', 'CUSTOMER', true, '[]')",
        {"id": UUID("80000000-0000-0000-0000-000000000004"), "user": STAFF_ID},
    )
    await must_reject(
        connection,
        "UPDATE notification_preferences SET identity_context='INVALID' "
        "WHERE user_id=:user",
        {"user": STAFF_ID},
    )


async def assert_0046(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0046)
    assert (
        await scalar(
            connection,
            "SELECT policy_version FROM product_packages WHERE id=:id",
            {"id": PACKAGE_ID},
        )
        == 1
    )
    await connection.execute(
        text(
            "INSERT INTO product_packages (id, request_id, package_version, "
            "creation_key, author_user_id, status) VALUES "
            "(:id, :request, 2, :creation_key, :staff, 'DRAFT')"
        ),
        {
            "id": SECOND_PACKAGE_ID,
            "request": MANAGED_REQUEST_ID,
            "creation_key": UUID("40000000-0000-0000-0000-000000000012"),
            "staff": STAFF_ID,
        },
    )
    assert (
        await scalar(
            connection,
            "SELECT policy_version FROM product_packages WHERE id=:id",
            {"id": SECOND_PACKAGE_ID},
        )
        == 2
    )
    await must_reject(
        connection,
        "UPDATE product_packages SET policy_version=3 WHERE id=:id",
        {"id": PACKAGE_ID},
    )


async def assert_0047(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0047)
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM saved_action_views WHERE identity_context='STAFF'",
        )
        == 2
    )
    await connection.execute(
        text(
            "INSERT INTO saved_action_views (id, owner_user_id, identity_context, "
            "name, filters, visible_columns) VALUES "
            "(:collision, :staff, 'CUSTOMER', 'Shared migration view', "
            "'{\"section\":\"CUSTOMER_COLLISION\"}', '[]'), "
            "(:customer_only, :staff, 'CUSTOMER', 'Customer-only migration view', "
            "'{\"section\":\"CUSTOMER_ONLY\"}', '[]')"
        ),
        {
            "collision": UUID("90000000-0000-0000-0000-000000000003"),
            "customer_only": UUID("90000000-0000-0000-0000-000000000004"),
            "staff": STAFF_ID,
        },
    )
    await must_reject(
        connection,
        "INSERT INTO saved_action_views (id, owner_user_id, identity_context, name, "
        "filters, visible_columns) VALUES (:id, :staff, 'CUSTOMER', "
        "'Shared migration view', '{}', '[]')",
        {"id": UUID("90000000-0000-0000-0000-000000000005"), "staff": STAFF_ID},
    )
    await must_reject(
        connection,
        "UPDATE saved_action_views SET identity_context='INVALID' "
        "WHERE owner_user_id=:staff",
        {"staff": STAFF_ID},
    )
