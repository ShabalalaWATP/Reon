"""Planning cockpit records and content-free analytics extensions.

Revision ID: 0015_planning_analytics
Revises: 0014_configuration_versions
Create Date: 2026-08-07 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_planning_analytics"
down_revision: str | None = "0014_configuration_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _id_and_timestamps(*, updated: bool = False) -> list[sa.Column[object]]:
    columns: list[sa.Column[object]] = [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]
    if updated:
        columns.append(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
    return columns


def upgrade() -> None:
    _create_template_tables()
    _create_package_planning_tables()
    _create_scenario_tables()
    _create_analytics_tables()


def _create_template_tables() -> None:
    op.create_table(
        "package_templates",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_id_and_timestamps(updated=True),
        sa.CheckConstraint("version > 0", name="package_template_version"),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "name", "version"),
    )
    op.create_index("ix_package_templates_team_id", "package_templates", ["team_id"])
    op.create_index(
        "ix_package_templates_team_active",
        "package_templates",
        ["team_id", "is_active"],
    )
    op.create_table(
        "package_template_checklist_items",
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(240), nullable=False),
        sa.Column(
            "required",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        *_id_and_timestamps(),
        sa.CheckConstraint("position >= 0", name="template_checklist_position"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["package_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "position"),
    )
    op.create_index(
        "ix_package_template_checklist_items_template_id",
        "package_template_checklist_items",
        ["template_id"],
    )


def _create_package_planning_tables() -> None:
    op.create_table(
        "package_checklists",
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid()),
        sa.Column("template_name", sa.String(100), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_id_and_timestamps(updated=True),
        sa.CheckConstraint("template_version > 0", name="checklist_template_version"),
        sa.CheckConstraint("version > 0", name="package_checklist_version"),
        sa.ForeignKeyConstraint(
            ["package_id"], ["work_packages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["package_templates.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package_id"),
    )
    op.create_index(
        "ix_package_checklists_package_id", "package_checklists", ["package_id"]
    )
    op.create_table(
        "package_checklist_items",
        sa.Column("checklist_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(240), nullable=False),
        sa.Column(
            "required",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by_user_id", sa.Uuid()),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_id_and_timestamps(updated=True),
        sa.CheckConstraint("position >= 0", name="package_checklist_item_position"),
        sa.CheckConstraint("version > 0", name="package_checklist_item_version"),
        sa.ForeignKeyConstraint(
            ["checklist_id"], ["package_checklists.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["completed_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checklist_id", "position"),
    )
    op.create_index(
        "ix_package_checklist_items_checklist_id",
        "package_checklist_items",
        ["checklist_id"],
    )
    op.create_table(
        "package_blockers",
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by_user_id", sa.Uuid()),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_id_and_timestamps(updated=True),
        sa.CheckConstraint("version > 0", name="package_blocker_version"),
        sa.CheckConstraint(
            "(resolved_at IS NULL AND resolved_by_user_id IS NULL) OR "
            "(resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)",
            name="package_blocker_resolution_shape",
        ),
        sa.ForeignKeyConstraint(
            ["package_id"], ["work_packages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["opened_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_package_blockers_package_id", "package_blockers", ["package_id"]
    )
    op.create_index("ix_package_blockers_team_id", "package_blockers", ["team_id"])
    op.create_index(
        "ix_package_blockers_team_opened",
        "package_blockers",
        ["team_id", "resolved_at"],
    )


def _create_scenario_tables() -> None:
    op.create_table(
        "planning_scenarios",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("planned_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _enum(
                "DRAFT",
                "PREVIEWED",
                "COMMITTED",
                name="planning_scenario_status",
            ),
            nullable=False,
        ),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_id_and_timestamps(updated=True),
        sa.CheckConstraint("ends_on >= starts_on", name="planning_scenario_window"),
        sa.CheckConstraint("planned_minutes > 0", name="planning_scenario_minutes"),
        sa.CheckConstraint("source_version > 0", name="planning_scenario_source"),
        sa.CheckConstraint("version > 0", name="planning_scenario_version"),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "name", "version"),
    )
    op.create_index("ix_planning_scenarios_team_id", "planning_scenarios", ["team_id"])
    op.create_index("ix_planning_scenarios_status", "planning_scenarios", ["status"])
    op.create_index(
        "ix_planning_scenarios_team_updated",
        "planning_scenarios",
        ["team_id", "updated_at"],
    )
    op.create_table(
        "planning_capacity_previews",
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("baseline", sa.JSON(), nullable=False),
        sa.Column("scenario", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        *_id_and_timestamps(),
        sa.CheckConstraint("expires_at > created_at", name="planning_preview_expiry"),
        sa.CheckConstraint("source_version > 0", name="planning_preview_source"),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["planning_scenarios.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("scenario_id", "team_id", "created_by_user_id"):
        op.create_index(
            f"ix_planning_capacity_previews_{column}",
            "planning_capacity_previews",
            [column],
        )
    op.create_index(
        "ix_planning_capacity_previews_token",
        "planning_capacity_previews",
        ["token"],
        unique=True,
    )
    op.create_table(
        "iteration_summary_snapshots",
        sa.Column("iteration_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("committed_packages", sa.Integer(), nullable=False),
        sa.Column("completed_packages", sa.Integer(), nullable=False),
        sa.Column("committed_points", sa.Integer(), nullable=False),
        sa.Column("completed_points", sa.Integer(), nullable=False),
        sa.Column("factual_summary", sa.String(240), nullable=False),
        *_id_and_timestamps(),
        sa.CheckConstraint("source_version > 0", name="iteration_summary_version"),
        sa.CheckConstraint(
            "committed_packages >= completed_packages",
            name="iteration_summary_package_counts",
        ),
        sa.CheckConstraint(
            "committed_points >= completed_points",
            name="iteration_summary_point_counts",
        ),
        sa.ForeignKeyConstraint(
            ["iteration_id"], ["team_iterations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("iteration_id", "source_version"),
    )
    op.create_index(
        "ix_iteration_summary_snapshots_iteration_id",
        "iteration_summary_snapshots",
        ["iteration_id"],
    )
    op.create_index(
        "ix_iteration_summary_snapshots_team_id",
        "iteration_summary_snapshots",
        ["team_id"],
    )


def _create_analytics_tables() -> None:
    op.create_table(
        "analytics_definition_versions",
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("unit", sa.String(24), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        *_id_and_timestamps(),
        sa.CheckConstraint("version > 0", name="analytics_definition_version"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "version"),
    )
    op.create_index(
        "ix_analytics_definition_versions_key",
        "analytics_definition_versions",
        ["key"],
    )
    fact_values = (
        "NOTIFICATION_SENT",
        "NOTIFICATION_RESPONDED",
        "DISSEMINATION_RELEASED",
        "DISSEMINATION_DOWNLOADED",
        "DISSEMINATION_LINK_OPENED",
        "DISSEMINATION_REPLACED",
        "DISSEMINATION_WITHDRAWN",
        "ITERATION_COMMITTED",
        "ITERATION_COMPLETED",
        "CAPACITY_AVAILABLE",
        "CAPACITY_RESERVED",
        "PLANNING_ACTIVE_WORK",
        "PLANNING_DEMAND",
    )
    op.create_table(
        "operational_analytics_facts",
        sa.Column("source_key", sa.String(160), nullable=False),
        sa.Column(
            "type", _enum(*fact_values, name="operational_fact_type"), nullable=False
        ),
        sa.Column("root_unit_id", sa.Uuid(), nullable=False),
        sa.Column("command_unit_id", sa.Uuid()),
        sa.Column("ops_unit_id", sa.Uuid()),
        sa.Column("team_unit_id", sa.Uuid()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count_value", sa.Integer(), server_default="1", nullable=False),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("measure_minutes", sa.Integer()),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        *_id_and_timestamps(),
        sa.CheckConstraint("count_value >= 0", name="operational_fact_count"),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="operational_fact_duration",
        ),
        sa.CheckConstraint(
            "measure_minutes IS NULL OR measure_minutes >= 0",
            name="operational_fact_minutes",
        ),
        sa.CheckConstraint(
            "definition_version > 0", name="operational_fact_definition"
        ),
        sa.CheckConstraint(
            "projection_version > 0", name="operational_fact_projection"
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key"),
    )
    op.create_index(
        "ix_operational_analytics_facts_type", "operational_analytics_facts", ["type"]
    )
    op.create_index(
        "ix_operational_analytics_facts_occurred_at",
        "operational_analytics_facts",
        ["occurred_at"],
    )
    for suffix, columns in (
        ("root_occurred", ["root_unit_id", "occurred_at"]),
        ("command_occurred", ["command_unit_id", "occurred_at"]),
        ("ops_occurred", ["ops_unit_id", "occurred_at"]),
        ("team_occurred", ["team_unit_id", "occurred_at"]),
        ("type_occurred", ["type", "occurred_at"]),
    ):
        op.create_index(
            f"ix_operational_facts_{suffix}",
            "operational_analytics_facts",
            columns,
        )
    export_statuses = ("PENDING", "DENIED", "READY", "FAILED", "EXPIRED")
    op.create_table(
        "analytics_aggregate_exports",
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("management_grant_id", sa.Uuid()),
        sa.Column("scope_unit_id", sa.Uuid(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("time_zone", sa.String(64), nullable=False),
        sa.Column(
            "format",
            _enum("CSV", "PDF", name="analytics_export_format"),
            nullable=False,
        ),
        sa.Column(
            "status",
            _enum(*export_statuses, name="analytics_export_status"),
            nullable=False,
        ),
        sa.Column("query_digest", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "cohort_suppressed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_id_and_timestamps(),
        sa.CheckConstraint("date_to >= date_from", name="analytics_export_window"),
        sa.CheckConstraint("row_count >= 0", name="analytics_export_rows"),
        sa.CheckConstraint("version > 0", name="analytics_export_version"),
        sa.CheckConstraint(
            "status <> 'READY' OR expires_at IS NOT NULL",
            name="analytics_export_ready_expiry",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["management_grant_id"], ["management_grants.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["scope_unit_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analytics_aggregate_exports_actor_user_id",
        "analytics_aggregate_exports",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_analytics_aggregate_exports_status",
        "analytics_aggregate_exports",
        ["status"],
    )
    op.create_index(
        "ix_analytics_exports_actor_created",
        "analytics_aggregate_exports",
        ["actor_user_id", "created_at"],
    )
    op.create_table(
        "analytics_export_audit_events",
        sa.Column("export_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "from_status",
            _enum(*export_statuses, name="analytics_export_event_from_status"),
        ),
        sa.Column(
            "to_status",
            _enum(*export_statuses, name="analytics_export_event_to_status"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(240), nullable=False),
        *_id_and_timestamps(),
        sa.CheckConstraint("sequence > 0", name="analytics_export_event_sequence"),
        sa.ForeignKeyConstraint(
            ["export_id"], ["analytics_aggregate_exports.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("export_id", "sequence"),
    )
    op.create_index(
        "ix_analytics_export_audit_events_export_id",
        "analytics_export_audit_events",
        ["export_id"],
    )


def downgrade() -> None:
    for table in (
        "analytics_export_audit_events",
        "analytics_aggregate_exports",
        "operational_analytics_facts",
        "analytics_definition_versions",
        "iteration_summary_snapshots",
        "planning_capacity_previews",
        "planning_scenarios",
        "package_blockers",
        "package_checklist_items",
        "package_checklists",
        "package_template_checklist_items",
        "package_templates",
    ):
        op.drop_table(table)
