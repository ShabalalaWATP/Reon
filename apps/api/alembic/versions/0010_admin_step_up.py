"""Session-bound Platform Administrator step-up authentication.

Revision ID: 0010_admin_step_up
Revises: 0009_related_records
Create Date: 2026-08-07 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_admin_step_up"
down_revision: str | None = "0009_related_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("elevated_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "elevated_until")
