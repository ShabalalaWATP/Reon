"""Unify routing and delivery workspace membership history.

Revision ID: 0024_unified_workspaces
Revises: 0023_cancellation_profiles
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_unified_workspaces"
down_revision: str | None = "0023_cancellation_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POSITION = sa.Enum(
    "MANAGER",
    "MEMBER",
    name="workspace_position",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    with op.batch_alter_table("team_memberships") as batch:
        batch.add_column(
            sa.Column(
                "workspace_position",
                POSITION,
                nullable=False,
                server_default="MEMBER",
            )
        )
        batch.drop_index("uq_team_memberships_one_open")
        batch.create_index(
            "uq_team_memberships_one_open",
            ["user_id", "team_id"],
            unique=True,
            postgresql_where=sa.text("effective_until IS NULL"),
            sqlite_where=sa.text("effective_until IS NULL"),
        )
        batch.create_index(
            "ix_team_memberships_workspace_position",
            ["workspace_position"],
            unique=False,
        )

    op.execute(
        sa.text(
            "UPDATE team_memberships SET workspace_position = 'MANAGER' "
            "WHERE user_id IN ("
            "SELECT id FROM users WHERE role = 'DELIVERY_TEAM_LEAD'"
            ")"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO team_memberships ("
            "id, user_id, team_id, workspace_position, effective_from, "
            "start_projected_at, started_by_user_id, start_reason, version, "
            "created_at, updated_at"
            ") SELECT "
            "m.id, m.user_id, m.unit_id, "
            "CASE WHEN u.username IN ('admin4', 'admin5', 'admin6', 'admin10') "
            "THEN 'MANAGER' ELSE 'MEMBER' END, "
            "m.created_at, m.created_at, NULL, "
            "'Migrated synthetic routing workspace membership.', 1, "
            "m.created_at, m.created_at "
            "FROM user_organisation_memberships m "
            "JOIN users u ON u.id = m.user_id "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM team_memberships tm "
            "WHERE tm.user_id = m.user_id AND tm.team_id = m.unit_id "
            "AND tm.effective_until IS NULL"
            ")"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM team_memberships WHERE team_id IN ("
            "SELECT id FROM organisation_units WHERE kind <> 'TEAM'"
            ")"
        )
    )
    # The former schema can represent only one open delivery-team membership
    # per user. Retain the most recent open record if post-upgrade administration
    # created several, so the structural downgrade remains executable.
    op.execute(
        sa.text(
            "DELETE FROM team_memberships WHERE id IN ("
            "SELECT id FROM ("
            "SELECT id, ROW_NUMBER() OVER ("
            "PARTITION BY user_id ORDER BY effective_from DESC, created_at DESC, id DESC"
            ") AS position FROM team_memberships WHERE effective_until IS NULL"
            ") ranked WHERE position > 1"
            ")"
        )
    )
    with op.batch_alter_table("team_memberships") as batch:
        batch.drop_index("ix_team_memberships_workspace_position")
        batch.drop_index("uq_team_memberships_one_open")
        batch.create_index(
            "uq_team_memberships_one_open",
            ["user_id"],
            unique=True,
            postgresql_where=sa.text("effective_until IS NULL"),
            sqlite_where=sa.text("effective_until IS NULL"),
        )
        batch.drop_column("workspace_position")
