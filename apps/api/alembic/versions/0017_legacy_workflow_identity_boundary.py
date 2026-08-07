"""Bound legacy unpinned workflow identity to pre-migration records.

Revision ID: 0017_legacy_workflow_identity
Revises: 0016_stable_team
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_legacy_workflow_identity"
down_revision: str | None = "0016_stable_team"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workflow_instances") as batch_op:
        batch_op.add_column(
            sa.Column(
                "legacy_unpinned_identity",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )
    connection = op.get_bind()
    workflow_instances = sa.table(
        "workflow_instances",
        sa.column("request_id", sa.Uuid()),
        sa.column("legacy_unpinned_identity", sa.Boolean()),
    )
    pins = sa.table(
        "request_configuration_pins",
        sa.column("request_id", sa.Uuid()),
    )
    pinned_ids = sa.select(pins.c.request_id)
    connection.execute(
        workflow_instances.update()
        .where(workflow_instances.c.request_id.not_in(pinned_ids))
        .values(legacy_unpinned_identity=True)
    )


def downgrade() -> None:
    with op.batch_alter_table("workflow_instances") as batch_op:
        batch_op.drop_column("legacy_unpinned_identity")
