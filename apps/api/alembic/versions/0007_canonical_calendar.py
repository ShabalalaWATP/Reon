"""Canonical workforce calendar and capacity snapshots.

Revision ID: 0007_calendar
Revises: 0006_team_memberships
Create Date: 2026-08-07 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_calendar"
down_revision: str | None = "0006_team_memberships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("subject_user_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            _enum("PERSONAL", "TEAM", "COMMITMENT", name="calendar_event_kind"),
            nullable=False,
        ),
        sa.Column(
            "category",
            _enum(
                "AVAILABILITY",
                "SERVICE_WORK",
                "LEAVE",
                "TRAINING",
                "DUTY",
                "APPOINTMENT",
                "OTHER",
                name="calendar_category",
            ),
            nullable=False,
        ),
        sa.Column(
            "visibility",
            _enum(
                "PRIVATE",
                "AVAILABILITY_ONLY",
                "TEAM_DETAIL",
                name="calendar_visibility",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_zone", sa.String(64), nullable=False),
        sa.Column(
            "all_day", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "recurrence",
            _enum("NONE", "DAILY", "WEEKLY", name="calendar_recurrence"),
            nullable=False,
        ),
        sa.Column(
            "recurrence_interval", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column("recurrence_until", sa.DateTime(timezone=True)),
        sa.Column(
            "status",
            _enum("ACTIVE", "CANCELLED", name="calendar_event_status"),
            nullable=False,
        ),
        sa.Column(
            "commitment_status",
            _enum(
                "NOT_REQUIRED",
                "PENDING",
                "ACKNOWLEDGED",
                "DISPUTED",
                name="commitment_status",
            ),
            nullable=False,
        ),
        sa.Column("commitment_reason", sa.Text()),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("ends_at > starts_at", name="calendar_event_window"),
        sa.CheckConstraint(
            "recurrence_interval BETWEEN 1 AND 4", name="calendar_recurrence_interval"
        ),
        sa.CheckConstraint("version > 0", name="calendar_event_version"),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("subject_user_id", "team_id", "kind", "status"):
        op.create_index(f"ix_calendar_events_{column}", "calendar_events", [column])
    op.create_index(
        "ix_calendar_events_subject_window",
        "calendar_events",
        ["subject_user_id", "starts_at", "recurrence_until"],
    )
    op.create_index(
        "ix_calendar_events_team_window",
        "calendar_events",
        ["team_id", "starts_at", "recurrence_until"],
    )

    op.create_table(
        "calendar_occurrence_exceptions",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("occurrence_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "kind",
            _enum("EDITED", "CANCELLED", name="calendar_exception_kind"),
            nullable=False,
        ),
        sa.Column("replacement_start", sa.DateTime(timezone=True)),
        sa.Column("replacement_end", sa.DateTime(timezone=True)),
        sa.Column("title", sa.String(160)),
        sa.Column("notes", sa.Text()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["calendar_events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id", "occurrence_start", name="calendar_occurrence_identity"
        ),
    )
    op.create_index(
        "ix_calendar_occurrence_exceptions_event_id",
        "calendar_occurrence_exceptions",
        ["event_id"],
    )

    op.create_table(
        "calendar_capacity_previews",
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("time_zone", sa.String(64), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("days", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_calendar_capacity_previews_token",
        "calendar_capacity_previews",
        ["token"],
        unique=True,
    )
    op.create_index(
        "ix_calendar_capacity_previews_team_id",
        "calendar_capacity_previews",
        ["team_id"],
    )

    op.create_table(
        "calendar_capacity_snapshots",
        sa.Column("preview_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("committed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("time_zone", sa.String(64), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("days", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["preview_id"], ["calendar_capacity_previews.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["committed_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("preview_id"),
    )
    op.create_index(
        "ix_calendar_capacity_snapshots_team_id",
        "calendar_capacity_snapshots",
        ["team_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_calendar_capacity_snapshots_team_id",
        table_name="calendar_capacity_snapshots",
    )
    op.drop_table("calendar_capacity_snapshots")
    op.drop_index(
        "ix_calendar_capacity_previews_team_id", table_name="calendar_capacity_previews"
    )
    op.drop_index(
        "ix_calendar_capacity_previews_token", table_name="calendar_capacity_previews"
    )
    op.drop_table("calendar_capacity_previews")
    op.drop_index(
        "ix_calendar_occurrence_exceptions_event_id",
        table_name="calendar_occurrence_exceptions",
    )
    op.drop_table("calendar_occurrence_exceptions")
    op.drop_index("ix_calendar_events_team_window", table_name="calendar_events")
    op.drop_index("ix_calendar_events_subject_window", table_name="calendar_events")
    for column in ("status", "kind", "team_id", "subject_user_id"):
        op.drop_index(f"ix_calendar_events_{column}", table_name="calendar_events")
    op.drop_table("calendar_events")


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)
