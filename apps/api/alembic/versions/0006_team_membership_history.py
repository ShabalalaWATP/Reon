"""Effective-dated team membership history and workspace activity.

Revision ID: 0006_team_memberships
Revises: 0005_management_analytics
Create Date: 2026-08-07 08:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_team_memberships"
down_revision: str | None = "0005_management_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "team_memberships",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True)),
        sa.Column("started_by_user_id", sa.Uuid()),
        sa.Column("start_reason", sa.Text(), nullable=False),
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
            "effective_until IS NULL OR effective_until > effective_from",
            name="team_membership_effective_window",
        ),
        sa.CheckConstraint("version > 0", name="team_membership_version"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["started_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ended_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_memberships_user_id", "team_memberships", ["user_id"])
    op.create_index("ix_team_memberships_team_id", "team_memberships", ["team_id"])
    op.create_index(
        "ix_team_memberships_team_window",
        "team_memberships",
        ["team_id", "effective_from", "effective_until"],
    )
    op.create_index(
        "uq_team_memberships_one_open",
        "team_memberships",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("effective_until IS NULL"),
        postgresql_where=sa.text("effective_until IS NULL"),
    )
    connection = op.get_bind()
    membership_rows = connection.execute(
        sa.text(
            "SELECT m.id, m.user_id, m.unit_id, m.created_at "
            "FROM user_organisation_memberships m "
            "JOIN users u ON u.id = m.user_id "
            "JOIN organisation_units o ON o.id = m.unit_id "
            "WHERE o.kind = 'TEAM' AND u.role IN "
            "('DELIVERY_TEAM_LEAD', 'DELIVERY_SPECIALIST')"
        )
    ).mappings()
    team_membership = sa.table(
        "team_memberships",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("team_id", sa.Uuid()),
        sa.column("effective_from", sa.DateTime(timezone=True)),
        sa.column("start_reason", sa.Text()),
        sa.column("version", sa.Integer()),
    )
    rows = [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "team_id": row["unit_id"],
            "effective_from": row["created_at"],
            "start_reason": "Imported from the established synthetic team baseline.",
            "version": 1,
        }
        for row in membership_rows
    ]
    if rows:
        op.bulk_insert(team_membership, rows)
    op.create_table(
        "team_activity_events",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("subject_user_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "MEMBER_ADDED",
                "MEMBERSHIP_ENDED",
                "TRANSFER_SCHEDULED",
                "TRANSFER_ACTIVATED",
                name="team_activity_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["membership_id"], ["team_memberships.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_team_activity_events_team_id", "team_activity_events", ["team_id"]
    )
    op.create_index("ix_team_activity_events_type", "team_activity_events", ["type"])
    op.create_index(
        "ix_team_activity_team_created",
        "team_activity_events",
        ["team_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_team_activity_team_created", table_name="team_activity_events")
    op.drop_index("ix_team_activity_events_type", table_name="team_activity_events")
    op.drop_index("ix_team_activity_events_team_id", table_name="team_activity_events")
    op.drop_table("team_activity_events")
    op.drop_index("uq_team_memberships_one_open", table_name="team_memberships")
    op.drop_index("ix_team_memberships_team_window", table_name="team_memberships")
    op.drop_index("ix_team_memberships_team_id", table_name="team_memberships")
    op.drop_index("ix_team_memberships_user_id", table_name="team_memberships")
    op.drop_table("team_memberships")
