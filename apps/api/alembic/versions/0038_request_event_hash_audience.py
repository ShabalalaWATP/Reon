"""Bind request-event audience into versioned audit hashes."""

import sqlalchemy as sa
from alembic import op

revision: str = "0038_request_event_hash_audience"
down_revision: str | None = "0037_audit_retention_security"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "request_events",
        sa.Column("hash_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "request_event_hash_version",
        "request_events",
        "hash_version IN (1, 2)",
    )


def downgrade() -> None:
    op.drop_constraint("request_event_hash_version", "request_events", type_="check")
    op.drop_column("request_events", "hash_version")
