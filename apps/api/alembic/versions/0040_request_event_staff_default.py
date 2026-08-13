"""Make unclassified request events staff-only by default."""

import sqlalchemy as sa
from alembic import op

revision: str = "0040_request_event_staff_default"
down_revision: str | None = "0039_retention_boundaries"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE request_events SET audience = 'STAFF_ONLY' "
            "WHERE hash_version = 1 AND (type IN ("
            "'task_hastener', 'workflow_assign', 'workflow_send_to_allocation', "
            "'workflow_hold', 'workflow_resume', 'workflow_close', "
            "'workflow_request_information', 'workflow_provide_information', "
            "'workflow_request_clarification', 'workflow_provide_clarification', "
            "'workflow_withdraw', "
            "'workflow_return_to_triage', 'workflow_return_to_coordination', "
            "'workflow_return_for_reallocation', 'workflow_changes_required', "
            "'PRODUCT_SUBMITTED', 'MANAGER_REVIEW_APPROVED', "
            "'PRODUCT_APPROVED', 'PRODUCT_REWORK_REQUESTED') "
            "OR type LIKE 'PRODUCT_%_REVIEW%')"
        )
    )
    op.alter_column(
        "request_events",
        "audience",
        existing_type=sa.String(length=18),
        server_default="STAFF_ONLY",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "request_events",
        "audience",
        existing_type=sa.String(length=18),
        server_default="CUSTOMER_AND_STAFF",
        existing_nullable=False,
    )
