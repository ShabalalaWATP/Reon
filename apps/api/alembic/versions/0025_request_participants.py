"""Add accountable request Lead and Contributor assignments.

Revision ID: 0025_request_participants
Revises: 0024_unified_workspaces
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_request_participants"
down_revision: str | None = "0024_unified_workspaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "request_participants",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "LEAD",
                "CONTRIBUTOR",
                name="request_participant_role",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("assigned_by_user_id", sa.Uuid()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("ended_by_user_id", sa.Uuid()),
        sa.Column("end_reason", sa.Text()),
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
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= effective_from",
            name=op.f("ck_request_participants_request_participant_window"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_request_participants_request_participant_version"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ended_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_request_participants_active_user",
        "request_participants",
        ["request_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
        sqlite_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        "uq_request_participants_active_lead",
        "request_participants",
        ["request_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL AND role = 'LEAD'"),
        sqlite_where=sa.text("ended_at IS NULL AND role = 'LEAD'"),
    )
    op.create_index(
        "ix_request_participants_user_active",
        "request_participants",
        ["user_id", "ended_at"],
    )
    op.create_index(
        op.f("ix_request_participants_request_id"),
        "request_participants",
        ["request_id"],
    )
    op.create_index(
        op.f("ix_request_participants_user_id"),
        "request_participants",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_request_participants_role"),
        "request_participants",
        ["role"],
    )
    op.execute(
        sa.text(
            "INSERT INTO request_participants ("
            "id, request_id, user_id, role, assigned_by_user_id, reason, "
            "effective_from, version, created_at, updated_at"
            ") SELECT id, id, assigned_specialist_id, 'LEAD', NULL, "
            "'Backfilled from the accountable Analyst assignment.', "
            "updated_at, 1, updated_at, updated_at FROM service_requests "
            "WHERE assigned_specialist_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_table("request_participants")
