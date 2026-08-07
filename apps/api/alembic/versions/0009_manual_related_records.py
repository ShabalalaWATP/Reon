"""Append-only manual related-record links.

Revision ID: 0009_related_records
Revises: 0008_team_planning
Create Date: 2026-08-07 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_related_records"
down_revision: str | None = "0008_team_planning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "request_links",
        sa.Column("source_request_id", sa.Uuid(), nullable=False),
        sa.Column("target_request_id", sa.Uuid(), nullable=False),
        sa.Column(
            "link_type",
            sa.Enum(
                "POSSIBLE_DUPLICATE",
                "RELATED_REQUEST",
                "EXISTING_OUTPUT",
                name="request_link_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_display_name", sa.String(120), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_request_id <> target_request_id",
            name="different_request",
        ),
        sa.ForeignKeyConstraint(
            ["source_request_id"], ["service_requests.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_request_id"], ["service_requests.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_request_id",
            "target_request_id",
            "link_type",
            name="uq_request_links_source_target_type",
        ),
    )
    op.create_index(
        "ix_request_links_source_request_id",
        "request_links",
        ["source_request_id"],
    )
    op.create_index(
        "ix_request_links_target_request_id",
        "request_links",
        ["target_request_id"],
    )
    op.create_index(
        "ix_request_links_link_type",
        "request_links",
        ["link_type"],
    )
    op.create_index(
        "ix_request_links_created_by_user_id",
        "request_links",
        ["created_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_request_links_created_by_user_id", table_name="request_links")
    op.drop_index("ix_request_links_link_type", table_name="request_links")
    op.drop_index("ix_request_links_target_request_id", table_name="request_links")
    op.drop_index("ix_request_links_source_request_id", table_name="request_links")
    op.drop_table("request_links")
