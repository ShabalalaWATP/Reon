"""Explicit management grants and content-free analytics foundations.

Revision ID: 0005_management_analytics
Revises: 0004_clarifications
Create Date: 2026-08-07 04:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_management_analytics"
down_revision: str | None = "0004_clarifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUEST_STATUSES = (
    "ROUTING_PENDING",
    "TRIAGE_REVIEW",
    "INFORMATION_REQUIRED",
    "COORDINATION_REVIEW",
    "ON_HOLD",
    "ALLOCATION_REVIEW",
    "DELIVERY_PLANNING",
    "IN_PROGRESS",
    "CUSTOMER_INFORMATION_REQUIRED",
    "LEAD_REVIEW",
    "REWORK_REQUIRED",
    "QUALITY_REVIEW",
    "READY_FOR_RELEASE",
    "COMPLETED",
    "CLOSED_NOT_PROGRESSED",
    "CANCELLED",
)


def _request_status(name: str) -> sa.Enum:
    return sa.Enum(
        *REQUEST_STATUSES, name=name, native_enum=False, create_constraint=True
    )


def upgrade() -> None:
    op.create_table(
        "organisation_closure",
        sa.Column("ancestor_id", sa.Uuid(), nullable=False),
        sa.Column("descendant_id", sa.Uuid(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.CheckConstraint("depth >= 0", name="organisation_closure_depth"),
        sa.ForeignKeyConstraint(
            ["ancestor_id"], ["organisation_units.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["descendant_id"], ["organisation_units.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("ancestor_id", "descendant_id"),
    )
    op.create_index(
        "ix_organisation_closure_descendant",
        "organisation_closure",
        ["descendant_id", "depth"],
    )
    op.create_table(
        "management_grants",
        sa.Column("subject_user_id", sa.Uuid(), nullable=False),
        sa.Column("root_unit_id", sa.Uuid(), nullable=False),
        sa.Column(
            "include_descendants",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True)),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("supersedes_grant_id", sa.Uuid()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by_user_id", sa.Uuid()),
        sa.Column("revocation_reason", sa.Text()),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("version > 0", name="management_grant_version"),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="management_grant_effective_window",
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL AND revocation_reason IS NOT NULL)",
            name="management_grant_revocation_shape",
        ),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["root_unit_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_grant_id"], ["management_grants.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_management_grants_subject_user_id", "management_grants", ["subject_user_id"]
    )
    op.create_index(
        "ix_management_grants_root_unit_id", "management_grants", ["root_unit_id"]
    )
    op.create_index(
        "ix_management_grants_subject_window",
        "management_grants",
        ["subject_user_id", "effective_from", "effective_until"],
    )
    op.create_table(
        "management_grant_actions",
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "STATISTICS",
                "ROSTER",
                "CALENDAR",
                "BOARD",
                "CAPACITY",
                name="management_action",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["management_grants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("grant_id", "action"),
    )
    op.create_table(
        "request_analytics_facts",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("root_unit_id", sa.Uuid(), nullable=False),
        sa.Column("command_unit_id", sa.Uuid()),
        sa.Column("ops_unit_id", sa.Uuid()),
        sa.Column("team_unit_id", sa.Uuid()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("required_by", sa.Date(), nullable=False),
        sa.Column(
            "current_status",
            _request_status("analytics_request_status"),
            nullable=False,
        ),
        sa.Column("last_transition_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column(
            "clarification_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "clarification_response_seconds",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("rework_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "feedback_received",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("feedback_rating", sa.Integer()),
        sa.Column(
            "projection_version", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column(
            "source_event_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("projected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("clarification_count >= 0", name="fact_clarifications"),
        sa.CheckConstraint(
            "clarification_response_seconds >= 0",
            name="fact_clarification_response_seconds",
        ),
        sa.CheckConstraint("rework_count >= 0", name="fact_rework"),
        sa.CheckConstraint(
            "feedback_rating IS NULL OR feedback_rating BETWEEN 1 AND 5",
            name="fact_feedback_rating",
        ),
        sa.CheckConstraint("projection_version > 0", name="fact_projection_version"),
        sa.CheckConstraint("source_event_count >= 0", name="fact_source_event_count"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["root_unit_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["command_unit_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ops_unit_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["team_unit_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("request_id"),
    )
    op.create_index(
        "ix_request_analytics_facts_received_at",
        "request_analytics_facts",
        ["received_at"],
    )
    op.create_index(
        "ix_request_analytics_facts_required_by",
        "request_analytics_facts",
        ["required_by"],
    )
    op.create_index(
        "ix_request_analytics_facts_current_status",
        "request_analytics_facts",
        ["current_status"],
    )
    op.create_index(
        "ix_request_facts_received_status",
        "request_analytics_facts",
        ["received_at", "current_status"],
    )
    op.create_index(
        "ix_request_facts_command_received",
        "request_analytics_facts",
        ["command_unit_id", "received_at"],
    )
    op.create_index(
        "ix_request_facts_ops_received",
        "request_analytics_facts",
        ["ops_unit_id", "received_at"],
    )
    op.create_index(
        "ix_request_facts_team_received",
        "request_analytics_facts",
        ["team_unit_id", "received_at"],
    )
    op.create_table(
        "request_stage_intervals",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", _request_status("analytics_stage_status"), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("source_event_id", sa.Uuid()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("sequence > 0", name="stage_interval_sequence"),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at", name="stage_interval_window"
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="stage_interval_duration",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"], ["request_events.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "sequence"),
    )
    op.create_index(
        "ix_request_stage_intervals_request_id",
        "request_stage_intervals",
        ["request_id"],
    )
    op.create_index(
        "ix_request_stage_intervals_unit_id", "request_stage_intervals", ["unit_id"]
    )
    op.create_index(
        "ix_stage_intervals_status_started",
        "request_stage_intervals",
        ["status", "started_at"],
    )
    op.create_index(
        "ix_stage_intervals_unit_started",
        "request_stage_intervals",
        ["unit_id", "started_at"],
    )
    op.create_table(
        "analytics_projection_state",
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column(
            "health",
            sa.Enum(
                "READY",
                "REBUILDING",
                "DEGRADED",
                name="analytics_projection_health",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "source_event_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "projected_request_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("last_projected_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("analytics_projection_state")
    op.drop_index(
        "ix_stage_intervals_unit_started", table_name="request_stage_intervals"
    )
    op.drop_index(
        "ix_stage_intervals_status_started", table_name="request_stage_intervals"
    )
    op.drop_index(
        "ix_request_stage_intervals_unit_id", table_name="request_stage_intervals"
    )
    op.drop_index(
        "ix_request_stage_intervals_request_id", table_name="request_stage_intervals"
    )
    op.drop_table("request_stage_intervals")
    op.drop_index(
        "ix_request_facts_team_received", table_name="request_analytics_facts"
    )
    op.drop_index("ix_request_facts_ops_received", table_name="request_analytics_facts")
    op.drop_index(
        "ix_request_facts_command_received", table_name="request_analytics_facts"
    )
    op.drop_index(
        "ix_request_facts_received_status", table_name="request_analytics_facts"
    )
    op.drop_index(
        "ix_request_analytics_facts_current_status",
        table_name="request_analytics_facts",
    )
    op.drop_index(
        "ix_request_analytics_facts_required_by", table_name="request_analytics_facts"
    )
    op.drop_index(
        "ix_request_analytics_facts_received_at", table_name="request_analytics_facts"
    )
    op.drop_table("request_analytics_facts")
    op.drop_table("management_grant_actions")
    op.drop_index("ix_management_grants_subject_window", table_name="management_grants")
    op.drop_index("ix_management_grants_root_unit_id", table_name="management_grants")
    op.drop_index(
        "ix_management_grants_subject_user_id", table_name="management_grants"
    )
    op.drop_table("management_grants")
    op.drop_index(
        "ix_organisation_closure_descendant", table_name="organisation_closure"
    )
    op.drop_table("organisation_closure")
