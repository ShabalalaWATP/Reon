"""Add worker, external-operation and keyset scaling foundations.

Revision ID: 0019_runtime_scaling
Revises: 0018_configuration_sealing
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_runtime_scaling"
down_revision: str | None = "0018_configuration_sealing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maintenance_job_states",
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.CheckConstraint(
            "lease_generation >= 0",
            name="maintenance_lease_generation_nonnegative",
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_index(
        "ix_maintenance_job_states_lease_expires_at",
        "maintenance_job_states",
        ["lease_expires_at"],
    )
    op.bulk_insert(
        sa.table("maintenance_job_states", sa.column("name", sa.String())),
        [
            {"name": "worker-heartbeat"},
            {"name": "workflow-start-dispatch"},
            {"name": "workflow-command-dispatch"},
            {"name": "workflow-reconciliation"},
            {"name": "notification-projection"},
            {"name": "membership-projection"},
        ],
    )

    with op.batch_alter_table("team_memberships") as batch:
        batch.add_column(
            sa.Column("start_projected_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("end_projected_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.create_index(
        "ix_team_memberships_due_start",
        "team_memberships",
        ["effective_from", "user_id"],
        postgresql_where=sa.text("start_projected_at IS NULL"),
    )
    op.create_index(
        "ix_team_memberships_due_end",
        "team_memberships",
        ["effective_until", "user_id"],
        postgresql_where=sa.text(
            "end_projected_at IS NULL AND effective_until IS NOT NULL"
        ),
    )

    with op.batch_alter_table("product_upload_intents") as batch:
        batch.add_column(
            sa.Column("operation_lease_owner", sa.String(length=64), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "operation_lease_generation",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "operation_lease_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch.create_check_constraint(
            "product_upload_operation_lease_generation_nonnegative",
            "operation_lease_generation >= 0",
        )
    op.create_index(
        "ix_product_upload_intents_operation_lease",
        "product_upload_intents",
        ["operation_lease_expires_at", "id"],
    )

    _create_feed_indexes()


def _create_feed_indexes() -> None:
    indexes = (
        (
            "ix_service_requests_requester_updated_id",
            "service_requests",
            ["requester_id", "updated_at", "id"],
        ),
        (
            "ix_service_requests_updated_id",
            "service_requests",
            ["updated_at", "id"],
        ),
        (
            "ix_request_routes_unit_position_request",
            "request_route_selections",
            ["unit_id", "position", "request_id"],
        ),
        (
            "ix_request_drafts_requester_updated_id",
            "request_drafts",
            ["requester_id", "updated_at", "id"],
        ),
        (
            "ix_workflow_tasks_role_status_updated_id",
            "workflow_tasks",
            ["candidate_role", "status", "updated_at", "id"],
        ),
        (
            "ix_request_events_request_created_id",
            "request_events",
            ["request_id", "created_at", "id"],
        ),
        ("ix_users_updated_id", "users", ["updated_at", "id"]),
        (
            "ix_analytics_team_request",
            "request_analytics_facts",
            ["team_unit_id", "request_id"],
        ),
        (
            "ix_work_packages_team_updated_id",
            "work_packages",
            ["team_id", "updated_at", "id"],
        ),
        (
            "ix_workflow_outbox_dispatch",
            "workflow_outbox",
            ["status", "available_at", "created_at", "id"],
        ),
    )
    for name, table, columns in indexes:
        op.create_index(name, table, list(columns))


def downgrade() -> None:
    for name, table in (
        ("ix_workflow_outbox_dispatch", "workflow_outbox"),
        ("ix_work_packages_team_updated_id", "work_packages"),
        ("ix_analytics_team_request", "request_analytics_facts"),
        ("ix_users_updated_id", "users"),
        ("ix_request_events_request_created_id", "request_events"),
        ("ix_workflow_tasks_role_status_updated_id", "workflow_tasks"),
        ("ix_request_drafts_requester_updated_id", "request_drafts"),
        ("ix_service_requests_updated_id", "service_requests"),
        ("ix_request_routes_unit_position_request", "request_route_selections"),
        ("ix_service_requests_requester_updated_id", "service_requests"),
    ):
        op.drop_index(name, table_name=table)
    op.drop_index(
        "ix_product_upload_intents_operation_lease",
        table_name="product_upload_intents",
    )
    with op.batch_alter_table("product_upload_intents") as batch:
        batch.drop_constraint(
            "product_upload_operation_lease_generation_nonnegative",
            type_="check",
        )
        batch.drop_column("operation_lease_expires_at")
        batch.drop_column("operation_lease_generation")
        batch.drop_column("operation_lease_owner")
    op.drop_index("ix_team_memberships_due_end", table_name="team_memberships")
    op.drop_index("ix_team_memberships_due_start", table_name="team_memberships")
    with op.batch_alter_table("team_memberships") as batch:
        batch.drop_column("end_projected_at")
        batch.drop_column("start_projected_at")
    op.drop_index(
        "ix_maintenance_job_states_lease_expires_at",
        table_name="maintenance_job_states",
    )
    op.drop_table("maintenance_job_states")
