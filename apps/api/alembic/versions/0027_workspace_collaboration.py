"""Add bounded workspace handover and decision records.

Revision ID: 0027_workspace_collaboration
Revises: 0026_calendar_ticket_links
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_workspace_collaboration"
down_revision: str | None = "0026_calendar_ticket_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_records",
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "DESCRIPTION",
                "HANDOVER",
                "RISK",
                "BLOCKER",
                "DECISION",
                "LINK",
                name="workspace_record_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "RESOLVED",
                name="workspace_record_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=500)),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("resolved_by_user_id", sa.Uuid()),
        sa.Column("resolution", sa.Text()),
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
            "version > 0", name=op.f("ck_workspace_records_workspace_record_version")
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["organisation_units.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_workspace_records_unit_id"), "workspace_records", ["unit_id"]
    )
    op.create_index(op.f("ix_workspace_records_kind"), "workspace_records", ["kind"])
    op.create_index(
        op.f("ix_workspace_records_status"), "workspace_records", ["status"]
    )
    op.create_index(
        "ix_workspace_records_unit_status",
        "workspace_records",
        ["unit_id", "status", "updated_at"],
    )
    op.create_table(
        "workspace_record_events",
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "CREATED",
                "RESOLVED",
                name="workspace_record_event_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["record_id"], ["workspace_records.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["organisation_units.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_workspace_record_events_record_id"),
        "workspace_record_events",
        ["record_id"],
    )
    op.create_index(
        op.f("ix_workspace_record_events_unit_id"),
        "workspace_record_events",
        ["unit_id"],
    )
    op.create_index(
        op.f("ix_workspace_record_events_type"),
        "workspace_record_events",
        ["type"],
    )
    op.create_index(
        "ix_workspace_record_events_record_created",
        "workspace_record_events",
        ["record_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("workspace_record_events")
    op.drop_table("workspace_records")
