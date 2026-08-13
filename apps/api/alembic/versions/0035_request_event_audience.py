"""Make request-event audience an enforceable projection boundary."""

import sqlalchemy as sa
from alembic import op

revision: str = "0035_request_event_audience"
down_revision: str | None = "0034_planning_concurrency"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "request_events",
        sa.Column(
            "audience",
            sa.String(length=18),
            nullable=False,
            server_default="CUSTOMER_AND_STAFF",
        ),
    )
    bind = op.get_bind()
    common = (
        "UPDATE request_events SET audience = 'STAFF_ONLY' "
        "WHERE type IN ('OWNERSHIP_RETURN_REQUESTED', "
        "'workflow_claimed', 'workflow_recovery_queued', "
        "'related_record_linked') OR (type = 'COORDINATION_MESSAGE' AND "
    )
    statement = (
        common + "json_extract(details, '$.audience') = 'CURRENT_OWNER')"
        if bind.dialect.name == "sqlite"
        else common + "details ->> 'audience' = 'CURRENT_OWNER')"
    )
    op.execute(sa.text(statement))
    op.create_check_constraint(
        "request_event_audience",
        "request_events",
        "audience IN ('CUSTOMER_AND_STAFF', 'STAFF_ONLY')",
    )
    op.create_index("ix_request_events_audience", "request_events", ["audience"])


def downgrade() -> None:
    op.drop_index("ix_request_events_audience", table_name="request_events")
    op.drop_constraint("request_event_audience", "request_events", type_="check")
    op.drop_column("request_events", "audience")
