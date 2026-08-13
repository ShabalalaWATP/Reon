"""Bound repeated security-denial evidence atomically."""

import sqlalchemy as sa
from alembic import op

revision: str = "0043_security_event_dedup"
down_revision: str | None = "0042_durable_password_assistance"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("security_events", sa.Column("deduplication_key", sa.String(64)))
    op.create_index(
        "ix_security_events_deduplication_key",
        "security_events",
        ["deduplication_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_security_events_deduplication_key", table_name="security_events")
    op.drop_column("security_events", "deduplication_key")
