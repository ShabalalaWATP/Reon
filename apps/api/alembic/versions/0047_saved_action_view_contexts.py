"""Namespace saved action views by effective identity context.

Revision ID: 0047_action_view_contexts
Revises: 0046_product_package_policy
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047_action_view_contexts"
down_revision: str | None = "0046_product_package_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "saved_action_views",
        sa.Column(
            "identity_context",
            sa.Enum(
                "CUSTOMER",
                "STAFF",
                name="saved_action_view_identity_context",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="STAFF",
            nullable=False,
        ),
    )
    op.drop_constraint(
        op.f("uq_saved_action_views_owner_user_id"),
        "saved_action_views",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_saved_action_views_owner_context_name",
        "saved_action_views",
        ["owner_user_id", "identity_context", "name"],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM saved_action_views AS customer "
        "WHERE customer.identity_context = 'CUSTOMER' AND EXISTS ("
        "SELECT 1 FROM saved_action_views AS staff "
        "WHERE staff.owner_user_id = customer.owner_user_id "
        "AND staff.name = customer.name "
        "AND staff.identity_context = 'STAFF')"
    )
    op.drop_constraint(
        "uq_saved_action_views_owner_context_name",
        "saved_action_views",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_saved_action_views_owner_user_id"),
        "saved_action_views",
        ["owner_user_id", "name"],
    )
    op.drop_column("saved_action_views", "identity_context")
