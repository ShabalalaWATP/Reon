"""Add the global managed-product storage reservation lock.

Revision ID: 0036_product_hardening
Revises: 0035_request_event_audience
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0036_product_hardening"
down_revision: str | None = "0035_request_event_audience"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "product_storage_quotas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cleanup_cursor", sa.String(length=255), nullable=True),
        sa.CheckConstraint("id = 1", name="product_storage_quota_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO product_storage_quotas (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("product_storage_quotas")
