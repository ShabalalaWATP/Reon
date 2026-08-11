"""Link Manager-created calendar commitments to service requests.

Revision ID: 0026_calendar_ticket_links
Revises: 0025_request_participants
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_calendar_ticket_links"
down_revision: str | None = "0025_request_participants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("calendar_events") as batch:
        batch.add_column(sa.Column("request_id", sa.Uuid()))
        batch.create_foreign_key(
            op.f("fk_calendar_events_request_id_service_requests"),
            "service_requests",
            ["request_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            op.f("ix_calendar_events_request_id"), ["request_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("calendar_events") as batch:
        batch.drop_index(op.f("ix_calendar_events_request_id"))
        batch.drop_constraint(
            op.f("fk_calendar_events_request_id_service_requests"),
            type_="foreignkey",
        )
        batch.drop_column("request_id")
