"""Pin immutable managed-product package policy versions.

Revision ID: 0046_product_package_policy
Revises: 0045_notification_contexts
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046_product_package_policy"
down_revision: str | None = "0045_notification_contexts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_packages",
        sa.Column("policy_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "product_package_policy_version",
        "product_packages",
        "policy_version IN (1, 2)",
    )
    op.alter_column("product_packages", "policy_version", server_default="2")


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_product_packages_product_package_policy_version"),
        "product_packages",
        type_="check",
    )
    op.drop_column("product_packages", "policy_version")
