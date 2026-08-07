"""Action workspace and durable in-application notifications.

Revision ID: 0012_action_notifications
Revises: 0011_operational_evidence
Create Date: 2026-08-07 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_action_notifications"
down_revision: str | None = "0011_operational_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id_and_timestamps(*, updated: bool = False) -> list[sa.Column[object]]:
    columns: list[sa.Column[object]] = [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]
    if updated:
        columns.append(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
    return columns


def upgrade() -> None:
    _create_action_projections()
    _create_saved_action_views()
    _create_notification_events()
    _create_notification_recipients()
    _create_notification_preferences()
    _create_projection_checkpoints()


def _create_action_projections() -> None:
    op.create_table(
        "action_projections",
        sa.Column("stable_key", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=21), nullable=False),
        sa.Column("source_id", sa.String(length=160), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_role", sa.String(length=21), nullable=True),
        sa.Column("required_scope", sa.String(length=120), nullable=True),
        sa.Column("organisation_unit_id", sa.Uuid(), nullable=True),
        sa.Column("section", sa.String(length=18), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("safe_title", sa.String(length=160), nullable=True),
        sa.Column("current_owner", sa.String(length=120), nullable=False),
        sa.Column("required_by", sa.Date(), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deep_link", sa.String(length=240), nullable=False),
        sa.Column("projected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_id_and_timestamps(updated=True),
        sa.CheckConstraint(
            "recipient_user_id IS NOT NULL OR candidate_role IS NOT NULL",
            name=op.f("ck_action_projections_action_audience"),
        ),
        sa.CheckConstraint(
            "source_version > 0",
            name=op.f("ck_action_projections_action_source_version"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_action_projections_action_version")
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organisation_unit_id"], ["organisation_units.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action_projections")),
        sa.UniqueConstraint(
            "stable_key", name=op.f("uq_action_projections_stable_key")
        ),
    )
    for columns in (
        ["request_id"],
        ["recipient_user_id"],
        ["candidate_role"],
        ["organisation_unit_id"],
        ["section"],
        ["action_type"],
        ["required_by"],
        ["last_changed_at"],
        ["is_active"],
    ):
        op.create_index(
            op.f(f"ix_action_projections_{columns[0]}"),
            "action_projections",
            columns,
        )
    op.create_index(
        "ix_action_projections_recipient_section_changed",
        "action_projections",
        ["recipient_user_id", "section", "last_changed_at"],
    )
    op.create_index(
        "ix_action_projections_role_unit_section",
        "action_projections",
        ["candidate_role", "organisation_unit_id", "section"],
    )


def _create_saved_action_views() -> None:
    op.create_table(
        "saved_action_views",
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("visible_columns", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_id_and_timestamps(updated=True),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_saved_action_views_saved_action_view_version")
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_action_views")),
        sa.UniqueConstraint(
            "owner_user_id", "name", name=op.f("uq_saved_action_views_owner_user_id")
        ),
    )
    op.create_index(
        op.f("ix_saved_action_views_owner_user_id"),
        "saved_action_views",
        ["owner_user_id"],
    )


def _create_notification_events() -> None:
    op.create_table(
        "notification_events",
        sa.Column("stable_key", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_group", sa.String(length=17), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=True),
        sa.Column("safe_subject", sa.String(length=180), nullable=False),
        sa.Column("deep_link", sa.String(length=240), nullable=True),
        sa.Column("audience", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", sa.String(length=9), server_default="PENDING", nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("projected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        *_id_and_timestamps(),
        sa.CheckConstraint(
            "source_version > 0",
            name=op.f("ck_notification_events_notification_source_version"),
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name=op.f("ck_notification_events_notification_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_requests.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_events")),
        sa.UniqueConstraint(
            "stable_key", name=op.f("uq_notification_events_stable_key")
        ),
    )
    for column in (
        "event_type",
        "event_group",
        "request_id",
        "occurred_at",
        "status",
        "available_at",
    ):
        op.create_index(
            op.f(f"ix_notification_events_{column}"), "notification_events", [column]
        )
    op.create_index(
        "ix_notification_events_status_available",
        "notification_events",
        ["status", "available_at"],
    )


def _create_notification_recipients() -> None:
    op.create_table(
        "notification_recipients",
        sa.Column("notification_event_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("access_kind", sa.String(length=12), nullable=False),
        sa.Column("required_role", sa.String(length=21), nullable=False),
        sa.Column("required_scope", sa.String(length=120), nullable=True),
        sa.Column("organisation_unit_id", sa.Uuid(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_id_and_timestamps(updated=True),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_notification_recipients_notification_recipient_version"),
        ),
        sa.ForeignKeyConstraint(
            ["notification_event_id"], ["notification_events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organisation_unit_id"],
            ["organisation_units.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_recipients")),
        sa.UniqueConstraint(
            "notification_event_id",
            "recipient_user_id",
            name=op.f("uq_notification_recipients_notification_event_id"),
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_notification_recipients_idempotency_key"),
        ),
    )
    for column in (
        "notification_event_id",
        "recipient_user_id",
        "organisation_unit_id",
    ):
        op.create_index(
            op.f(f"ix_notification_recipients_{column}"),
            "notification_recipients",
            [column],
        )
    op.create_index(
        "ix_notification_recipients_user_state",
        "notification_recipients",
        ["recipient_user_id", "archived_at", "read_at"],
    )


def _create_notification_preferences() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_group", sa.String(length=17), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("reminder_days", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_id_and_timestamps(updated=True),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_notification_preferences_notification_preference_version"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_preferences")),
        sa.UniqueConstraint(
            "user_id",
            "event_group",
            name=op.f("uq_notification_preferences_user_id"),
        ),
    )
    op.create_index(
        op.f("ix_notification_preferences_user_id"),
        "notification_preferences",
        ["user_id"],
    )


def _create_projection_checkpoints() -> None:
    op.create_table(
        "projection_checkpoints",
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("last_event_key", sa.String(length=160), nullable=True),
        sa.Column("source_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("projected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "health", sa.String(length=8), server_default="DEGRADED", nullable=False
        ),
        sa.CheckConstraint(
            "pending_count >= 0",
            name=op.f("ck_projection_checkpoints_projection_pending_count"),
        ),
        sa.CheckConstraint(
            "failed_count >= 0",
            name=op.f("ck_projection_checkpoints_projection_failed_count"),
        ),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_projection_checkpoints")),
    )


def downgrade() -> None:
    op.drop_table("projection_checkpoints")
    op.drop_index(
        op.f("ix_notification_preferences_user_id"),
        table_name="notification_preferences",
    )
    op.drop_table("notification_preferences")
    op.drop_index(
        "ix_notification_recipients_user_state",
        table_name="notification_recipients",
    )
    for column in (
        "organisation_unit_id",
        "recipient_user_id",
        "notification_event_id",
    ):
        op.drop_index(
            op.f(f"ix_notification_recipients_{column}"),
            table_name="notification_recipients",
        )
    op.drop_table("notification_recipients")
    op.drop_index(
        "ix_notification_events_status_available", table_name="notification_events"
    )
    for column in (
        "available_at",
        "status",
        "occurred_at",
        "request_id",
        "event_group",
        "event_type",
    ):
        op.drop_index(
            op.f(f"ix_notification_events_{column}"),
            table_name="notification_events",
        )
    op.drop_table("notification_events")
    op.drop_index(
        op.f("ix_saved_action_views_owner_user_id"), table_name="saved_action_views"
    )
    op.drop_table("saved_action_views")
    op.drop_index(
        "ix_action_projections_role_unit_section", table_name="action_projections"
    )
    op.drop_index(
        "ix_action_projections_recipient_section_changed",
        table_name="action_projections",
    )
    for column in (
        "is_active",
        "last_changed_at",
        "required_by",
        "action_type",
        "section",
        "organisation_unit_id",
        "candidate_role",
        "recipient_user_id",
        "request_id",
    ):
        op.drop_index(
            op.f(f"ix_action_projections_{column}"),
            table_name="action_projections",
        )
    op.drop_table("action_projections")
