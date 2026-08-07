"""bounded local platform administration

Revision ID: 0002_admin
Revises: 0001_initial
Create Date: 2026-08-06 23:58:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_admin"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "organisation_units",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_table(
        "admin_audit_anchors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("head_hash", sa.String(length=64), nullable=True),
        sa.Column("anchor_mac", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "(event_count = 0 AND head_hash IS NULL AND anchor_mac IS NULL) OR "
            "(event_count > 0 AND head_hash IS NOT NULL AND anchor_mac IS NOT NULL)",
            name=op.f("ck_admin_audit_anchors_admin_audit_anchor_consistency"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_audit_anchors"),
    )
    op.create_table(
        "admin_identity_sequences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("next_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_admin_identity_sequences"),
    )
    sequence_table = sa.table(
        "admin_identity_sequences",
        sa.column("id", sa.Integer()),
        sa.column("next_value", sa.Integer()),
    )
    op.bulk_insert(sequence_table, [{"id": 1, "next_value": 1}])
    op.create_table(
        "admin_audit_events",
        sa.Column("anchor_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_admin_audit_events_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["anchor_id"],
            ["admin_audit_anchors.id"],
            name="fk_admin_audit_events_anchor_id_admin_audit_anchors",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_audit_events"),
        sa.UniqueConstraint(
            "anchor_id", "sequence", name="uq_admin_audit_events_anchor_id"
        ),
        sa.UniqueConstraint("event_hash", name="uq_admin_audit_events_event_hash"),
    )
    op.create_index(
        "ix_admin_audit_events_actor_user_id",
        "admin_audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_admin_audit_events_anchor_id",
        "admin_audit_events",
        ["anchor_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_audit_events_anchor_id", table_name="admin_audit_events")
    op.drop_index(
        "ix_admin_audit_events_actor_user_id", table_name="admin_audit_events"
    )
    op.drop_table("admin_audit_events")
    op.drop_table("admin_audit_anchors")
    op.drop_table("admin_identity_sequences")
    op.drop_column("organisation_units", "version")
    op.drop_column("users", "version")
