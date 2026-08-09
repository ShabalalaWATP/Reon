"""Add distributed login rate-limit state.

Revision ID: 0020_login_rate_limits
Revises: 0019_runtime_scaling
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_login_rate_limits"
down_revision: str | None = "0019_runtime_scaling"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_rate_limits",
        sa.Column("scope_key", sa.String(length=72), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempt_count > 0",
            name="login_rate_limit_attempt_count_positive",
        ),
        sa.PrimaryKeyConstraint("scope_key"),
    )
    op.create_index(
        "ix_login_rate_limits_expires_at",
        "login_rate_limits",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_login_rate_limits_expires_at",
        table_name="login_rate_limits",
    )
    op.drop_table("login_rate_limits")
