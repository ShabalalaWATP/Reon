"""Enforce active capacity reservation non-overlap in PostgreSQL.

Revision ID: 0034_planning_concurrency
Revises: 0033_customer_product_acceptance
Create Date: 2026-08-13 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034_planning_concurrency"
down_revision: str | None = "0033_customer_product_acceptance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE capacity_reservations
        ADD CONSTRAINT capacity_reservations_active_no_overlap
        EXCLUDE USING gist (
            user_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (status = 'ACTIVE')
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE capacity_reservations DROP CONSTRAINT IF EXISTS "
        "capacity_reservations_active_no_overlap"
    )
