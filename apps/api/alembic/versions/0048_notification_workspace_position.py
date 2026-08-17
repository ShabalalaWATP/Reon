"""Retain the exact workspace position required by a notification recipient.

Revision ID: 0048_notification_position
Revises: 0047_action_view_contexts
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0048_notification_position"
down_revision: str | None = "0047_action_view_contexts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_recipients",
        sa.Column(
            "required_workspace_position",
            sa.Enum(
                "MANAGER",
                "MEMBER",
                name="notification_required_workspace_position",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE notification_recipients SET required_workspace_position = 'MANAGER' "
        "WHERE required_role = 'QUALITY_RELEASE'"
    )


def downgrade() -> None:
    op.drop_column("notification_recipients", "required_workspace_position")
