"""Customer drafts, idempotent submission and required feedback comments.

Revision ID: 0003_customer_quality
Revises: 0002_admin
Create Date: 2026-08-07 01:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_customer_quality"
down_revision: str | None = "0002_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("service_requests", sa.Column("submission_key", sa.Uuid()))
    op.create_index(
        "ix_service_requests_submission_key",
        "service_requests",
        ["submission_key"],
        unique=True,
    )
    op.add_column("feedback", sa.Column("submission_key", sa.Uuid()))
    op.create_index(
        "ix_feedback_submission_key", "feedback", ["submission_key"], unique=True
    )
    op.execute(
        sa.text(
            "UPDATE feedback SET comments = 'No comment provided.' "
            "WHERE comments IS NULL OR trim(comments) = ''"
        )
    )
    with op.batch_alter_table("feedback") as batch_op:
        batch_op.alter_column("comments", existing_type=sa.Text(), nullable=False)
    op.create_table(
        "request_drafts",
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=160)),
        sa.Column("service_category", sa.String(length=80)),
        sa.Column("description", sa.Text()),
        sa.Column("desired_outcome", sa.Text()),
        sa.Column("background_context", sa.Text()),
        sa.Column("required_by", sa.Date()),
        sa.Column("required_by_reason", sa.Text()),
        sa.Column("preferred_deliverable_type", sa.String(length=80)),
        sa.Column("success_criteria", sa.Text()),
        sa.Column("requesting_business_area", sa.String(length=120)),
        sa.Column("intended_recipients", sa.JSON()),
        sa.Column("sensitivity", sa.String(length=20)),
        sa.Column("handling_instructions", sa.Text()),
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
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            name="fk_request_drafts_requester_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_request_drafts"),
    )
    op.create_index(
        "ix_request_drafts_requester_id",
        "request_drafts",
        ["requester_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_request_drafts_requester_id", table_name="request_drafts")
    op.drop_table("request_drafts")
    with op.batch_alter_table("feedback") as batch_op:
        batch_op.alter_column("comments", existing_type=sa.Text(), nullable=True)
    op.drop_index("ix_feedback_submission_key", table_name="feedback")
    op.drop_column("feedback", "submission_key")
    op.drop_index("ix_service_requests_submission_key", table_name="service_requests")
    op.drop_column("service_requests", "submission_key")
