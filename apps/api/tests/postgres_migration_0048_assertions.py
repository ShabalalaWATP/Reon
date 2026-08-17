"""PostgreSQL evidence for position-scoped notification recipients."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from postgres_migration_probe import (
    REVISION_0048,
    assert_revision,
    column_exists,
    must_reject,
    scalar,
)
from postgres_migration_seed import (
    MANAGED_REQUEST_ID,
    QC_ACTIVE_ID,
    QC_TEAM_ID,
)

EVENT_ID = UUID("80000000-0000-0000-0000-000000000008")
RECIPIENT_ID = UUID("80000000-0000-0000-0000-000000000009")


async def seed_0048_legacy_recipient(connection: AsyncConnection) -> None:
    await connection.execute(
        text(
            "INSERT INTO notification_events (id, stable_key, event_type, "
            "event_group, source_version, request_id, safe_subject, audience, "
            "occurred_at, available_at) VALUES (:event, 'migration-qc-event', "
            "'TASK_ASSIGNED', 'ASSIGNMENT', 1, :request, "
            "'Synthetic QC assignment', '[]', now(), now())"
        ),
        {"event": EVENT_ID, "request": MANAGED_REQUEST_ID},
    )
    await connection.execute(
        text(
            "INSERT INTO notification_recipients (id, notification_event_id, "
            "recipient_user_id, idempotency_key, access_kind, required_role, "
            "required_scope, organisation_unit_id) VALUES (:id, :event, :user, "
            "'migration-qc-recipient', 'ROUTE_MEMBER', 'QUALITY_RELEASE', "
            "'Combined QC Team', :team)"
        ),
        {
            "id": RECIPIENT_ID,
            "event": EVENT_ID,
            "user": QC_ACTIVE_ID,
            "team": QC_TEAM_ID,
        },
    )


async def assert_0048(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0048)
    assert await column_exists(
        connection, "notification_recipients", "required_workspace_position"
    )
    assert (
        await scalar(
            connection,
            "SELECT required_workspace_position FROM notification_recipients "
            "WHERE id=:id",
            {"id": RECIPIENT_ID},
        )
        == "MANAGER"
    )
    await must_reject(
        connection,
        "UPDATE notification_recipients "
        "SET required_workspace_position='INVALID' WHERE id=:id",
        {"id": RECIPIENT_ID},
    )
