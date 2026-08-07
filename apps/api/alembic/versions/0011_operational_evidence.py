"""Append-only operational maintenance evidence.

Revision ID: 0011_operational_evidence
Revises: 0010_admin_step_up
Create Date: 2026-08-07 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_operational_evidence"
down_revision: str | None = "0010_admin_step_up"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_runs",
        sa.Column("job_name", sa.String(length=80), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("result_counts", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operational_runs")),
    )
    op.create_index(
        op.f("ix_operational_runs_job_name"),
        "operational_runs",
        ["job_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_operational_runs_job_name"), table_name="operational_runs")
    op.drop_table("operational_runs")
