"""Namespace notification preferences by effective identity context.

Revision ID: 0045_notification_contexts
Revises: 0044_context_conversations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0045_notification_contexts"
down_revision: str | None = "0044_context_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column(
            "identity_context",
            sa.Enum(
                "CUSTOMER",
                "STAFF",
                name="notification_preference_identity_context",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="STAFF",
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE notification_preferences SET identity_context = 'CUSTOMER' "
        "WHERE user_id IN (SELECT id FROM users WHERE role = 'REQUESTER')"
    )
    op.drop_constraint(
        op.f("uq_notification_preferences_user_id"),
        "notification_preferences",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_notification_preferences_user_context_group",
        "notification_preferences",
        ["user_id", "identity_context", "event_group"],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM notification_preferences AS customer "
        "WHERE customer.identity_context = 'CUSTOMER' AND EXISTS ("
        "SELECT 1 FROM notification_preferences AS staff "
        "WHERE staff.user_id = customer.user_id "
        "AND staff.event_group = customer.event_group "
        "AND staff.identity_context = 'STAFF')"
    )
    op.drop_constraint(
        "uq_notification_preferences_user_context_group",
        "notification_preferences",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_notification_preferences_user_id"),
        "notification_preferences",
        ["user_id", "event_group"],
    )
    op.drop_column("notification_preferences", "identity_context")
