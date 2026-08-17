"""Retention and accepted-loss assertions for migration downgrades."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncConnection

from postgres_migration_probe import (
    REVISION_0043,
    REVISION_0044,
    REVISION_0045,
    REVISION_0046,
    REVISION_0047,
    REVISION_0049,
    assert_revision,
    column_exists,
    scalar,
)
from postgres_migration_seed import PACKAGE_ID, QC_ACTIVE_ID, QC_TEAM_ID, STAFF_ID


async def assert_0048_downgrade(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0047)
    assert not await column_exists(
        connection, "notification_recipients", "required_workspace_position"
    )
    assert await scalar(connection, "SELECT count(*) FROM notification_recipients") == 1


async def assert_0047_downgrade(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0046)
    assert not await column_exists(connection, "saved_action_views", "identity_context")
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM saved_action_views WHERE owner_user_id=:staff "
            "AND name='Shared migration view'",
            {"staff": STAFF_ID},
        )
        == 1
    )
    assert (
        await scalar(
            connection,
            "SELECT filters->>'section' FROM saved_action_views "
            "WHERE owner_user_id=:staff AND name='Shared migration view'",
            {"staff": STAFF_ID},
        )
        == "NEEDS_ATTENTION"
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM saved_action_views "
            "WHERE name='Customer-only migration view'",
        )
        == 1
    )


async def assert_0046_downgrade(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0045)
    assert not await column_exists(connection, "product_packages", "policy_version")
    assert await scalar(connection, "SELECT count(*) FROM product_packages") == 2
    assert (
        await scalar(
            connection,
            "SELECT covering_note FROM product_packages WHERE id=:id",
            {"id": PACKAGE_ID},
        )
        == "Synthetic covering note"
    )


async def assert_0045_downgrade(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0044)
    assert not await column_exists(
        connection, "notification_preferences", "identity_context"
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM notification_preferences WHERE user_id=:staff "
            "AND event_group='REQUEST_LIFECYCLE'",
            {"staff": STAFF_ID},
        )
        == 1
    )
    assert (
        await scalar(
            connection,
            "SELECT enabled FROM notification_preferences WHERE user_id=:staff",
            {"staff": STAFF_ID},
        )
        is False
    )


async def assert_0044_downgrade(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0043)
    for table, column in (
        ("users", "customer_context_enabled"),
        ("sessions", "active_context"),
        ("sessions", "context_version"),
        ("service_requests", "product_mode"),
        ("product_packages", "covering_note"),
    ):
        assert not await column_exists(connection, table, column)
    assert (
        await scalar(
            connection, "SELECT to_regclass('public.request_conversations') IS NULL"
        )
        is True
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM team_memberships WHERE team_id=:team AND "
            "start_reason='0044 Combined QC Team membership backfill.'",
            {"team": QC_TEAM_ID},
        )
        == 0
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM team_memberships WHERE team_id=:team "
            "AND start_reason='Synthetic retained QC history'",
            {"team": QC_TEAM_ID},
        )
        == 1
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM user_organisation_memberships WHERE unit_id=:team",
            {"team": QC_TEAM_ID},
        )
        == 0
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM organisation_units WHERE id=:team",
            {"team": QC_TEAM_ID},
        )
        == 1
    )
    assert await scalar(connection, "SELECT count(*) FROM product_packages") == 2


async def assert_reupgrade(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0049)
    assert (
        await scalar(
            connection, "SELECT count(*) FROM product_packages WHERE policy_version=1"
        )
        == 2
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM product_packages WHERE covering_note IS NULL",
        )
        == 2
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM notification_preferences WHERE user_id=:staff "
            "AND identity_context='STAFF'",
            {"staff": STAFF_ID},
        )
        == 1
    )
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM saved_action_views WHERE identity_context='STAFF'",
        )
        == 3
    )
    assert await scalar(connection, "SELECT count(*) FROM request_conversations") == 0
    assert (
        await scalar(
            connection,
            "SELECT count(*) FROM team_memberships WHERE user_id=:user "
            "AND team_id=:team AND effective_until IS NULL",
            {"user": QC_ACTIVE_ID, "team": QC_TEAM_ID},
        )
        == 1
    )


async def assert_empty_forward_path(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0049)
    assert await scalar(connection, "SELECT count(*) FROM users") == 0
    assert (
        await scalar(
            connection, "SELECT to_regclass('public.request_conversations') IS NOT NULL"
        )
        is True
    )
