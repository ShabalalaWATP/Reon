"""Workflow-derived board and independent team agile planning.

Revision ID: 0008_team_planning
Revises: 0007_calendar
Create Date: 2026-08-07 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_team_planning"
down_revision: str | None = "0007_calendar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "team_iterations",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column(
            "status",
            _enum("PLANNED", "ACTIVE", "CLOSED", name="iteration_status"),
            nullable=False,
        ),
        sa.Column("completion_summary", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint("ends_on >= starts_on", name="iteration_window"),
        sa.CheckConstraint("version > 0", name="iteration_version"),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "name"),
    )
    op.create_index("ix_team_iterations_team_id", "team_iterations", ["team_id"])
    op.create_index("ix_team_iterations_status", "team_iterations", ["status"])

    op.create_table(
        "work_packages",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("linked_request_id", sa.Uuid()),
        sa.Column("iteration_id", sa.Uuid()),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_points", sa.Integer(), nullable=False),
        sa.Column("remaining_effort_minutes", sa.Integer(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column(
            "priority",
            _enum("LOW", "MEDIUM", "HIGH", "URGENT", name="work_package_priority"),
            nullable=False,
        ),
        sa.Column(
            "status",
            _enum(
                "BACKLOG",
                "READY",
                "IN_PROGRESS",
                "BLOCKED",
                "DONE",
                "CANCELLED",
                name="work_package_status",
            ),
            nullable=False,
        ),
        sa.Column("blockers", sa.Text(), nullable=False),
        sa.Column("acceptance_criteria", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "estimate_points BETWEEN 1 AND 100", name="package_estimate"
        ),
        sa.CheckConstraint(
            "remaining_effort_minutes >= 0", name="package_remaining_effort"
        ),
        sa.CheckConstraint("version > 0", name="package_version"),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["linked_request_id"], ["service_requests.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["iteration_id"], ["team_iterations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "team_id",
        "linked_request_id",
        "iteration_id",
        "owner_user_id",
        "due_on",
        "priority",
        "status",
    ):
        op.create_index(f"ix_work_packages_{column}", "work_packages", [column])
    op.create_index(
        "ix_work_packages_team_status_due",
        "work_packages",
        ["team_id", "status", "due_on"],
    )

    op.create_table(
        "work_package_contributors",
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["package_id"], ["work_packages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("package_id", "user_id"),
    )
    op.create_table(
        "work_package_dependencies",
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("depends_on_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "package_id <> depends_on_id", name="package_not_self_dependency"
        ),
        sa.ForeignKeyConstraint(
            ["package_id"], ["work_packages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_id"], ["work_packages.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("package_id", "depends_on_id"),
    )
    op.create_table(
        "work_package_activity",
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            _enum(
                "CREATED",
                "UPDATED",
                "MOVED",
                "RESERVATION_CREATED",
                "RESERVATION_CANCELLED",
                "ITERATION_CHANGED",
                name="work_package_activity_type",
            ),
            nullable=False,
        ),
        sa.Column("summary", sa.String(240), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        *_created_columns(),
        sa.ForeignKeyConstraint(
            ["package_id"], ["work_packages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_work_package_activity_package_id", "work_package_activity", ["package_id"]
    )
    op.create_index(
        "ix_work_package_activity_team_id", "work_package_activity", ["team_id"]
    )
    op.create_index(
        "ix_package_activity_package_created",
        "work_package_activity",
        ["package_id", "created_at"],
    )

    op.create_table(
        "capacity_reservations",
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _enum("ACTIVE", "CANCELLED", name="reservation_status"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("cancelled_by_user_id", sa.Uuid()),
        sa.Column("cancellation_reason", sa.Text()),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint("ends_at > starts_at", name="reservation_window"),
        sa.CheckConstraint("minutes > 0", name="reservation_minutes"),
        sa.CheckConstraint("version > 0", name="reservation_version"),
        sa.ForeignKeyConstraint(
            ["package_id"], ["work_packages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("package_id", "team_id", "user_id", "status"):
        op.create_index(
            f"ix_capacity_reservations_{column}", "capacity_reservations", [column]
        )
    op.create_index(
        "ix_capacity_reservations_user_window",
        "capacity_reservations",
        ["user_id", "starts_at", "ends_at"],
    )

    op.create_table(
        "team_board_configurations",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("wip_limits", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("team_id"),
    )
    op.create_table(
        "saved_board_views",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "owner_user_id", "name"),
    )
    op.create_index("ix_saved_board_views_team_id", "saved_board_views", ["team_id"])
    op.create_index(
        "ix_saved_board_views_owner_user_id", "saved_board_views", ["owner_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_saved_board_views_owner_user_id", table_name="saved_board_views")
    op.drop_index("ix_saved_board_views_team_id", table_name="saved_board_views")
    op.drop_table("saved_board_views")
    op.drop_table("team_board_configurations")
    op.drop_index(
        "ix_capacity_reservations_user_window", table_name="capacity_reservations"
    )
    for column in ("status", "user_id", "team_id", "package_id"):
        op.drop_index(
            f"ix_capacity_reservations_{column}", table_name="capacity_reservations"
        )
    op.drop_table("capacity_reservations")
    op.drop_index(
        "ix_package_activity_package_created", table_name="work_package_activity"
    )
    op.drop_index(
        "ix_work_package_activity_team_id", table_name="work_package_activity"
    )
    op.drop_index(
        "ix_work_package_activity_package_id", table_name="work_package_activity"
    )
    op.drop_table("work_package_activity")
    op.drop_table("work_package_dependencies")
    op.drop_table("work_package_contributors")
    op.drop_index("ix_work_packages_team_status_due", table_name="work_packages")
    for column in (
        "status",
        "priority",
        "due_on",
        "owner_user_id",
        "iteration_id",
        "linked_request_id",
        "team_id",
    ):
        op.drop_index(f"ix_work_packages_{column}", table_name="work_packages")
    op.drop_table("work_packages")
    op.drop_index("ix_team_iterations_status", table_name="team_iterations")
    op.drop_index("ix_team_iterations_team_id", table_name="team_iterations")
    op.drop_table("team_iterations")


def _created_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def _timestamp_columns() -> tuple[sa.Column, ...]:
    return (
        *_created_columns(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)
