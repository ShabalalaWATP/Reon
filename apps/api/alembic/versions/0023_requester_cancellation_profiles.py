"""Add bounded self-profile fields.

Revision ID: 0023_cancellation_profiles
Revises: 0022_customer_intake
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_cancellation_profiles"
down_revision: str | None = "0022_customer_intake"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("profile_team", sa.String(length=120)))
        batch.add_column(sa.Column("rank_or_grade", sa.String(length=120)))
        batch.add_column(sa.Column("service_number", sa.String(length=80)))
        batch.add_column(sa.Column("additional_information", sa.Text()))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("additional_information")
        batch.drop_column("service_number")
        batch.drop_column("rank_or_grade")
        batch.drop_column("profile_team")
