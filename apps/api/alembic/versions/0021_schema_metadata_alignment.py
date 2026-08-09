"""Align readable constraint names and performance indexes with ORM metadata.

Revision ID: 0021_schema_metadata
Revises: 0020_login_rate_limits
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_schema_metadata"
down_revision: str | None = "0020_login_rate_limits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CHECKS = (
    (
        "analytics_export_audit_events",
        "ck_analytics_export_audit_events_analytics_export_event_sequence",
        "ck_analytics_export_audit_events_sequence_positive",
        "sequence > 0",
    ),
    (
        "configuration_hierarchy_edges",
        "ck_configuration_hierarchy_edges_configuration_edge_distinct_units",
        "ck_configuration_hierarchy_edges_distinct_units",
        "parent_unit_id <> child_unit_id",
    ),
    (
        "configuration_hierarchy_edges",
        "ck_configuration_hierarchy_edges_configuration_edge_effective_window",
        "ck_configuration_hierarchy_edges_effective_window",
        "effective_until IS NULL OR effective_until > effective_from",
    ),
    (
        "configuration_unit_revisions",
        "ck_configuration_unit_revisions_configuration_unit_effective_window",
        "ck_configuration_unit_revisions_effective_window",
        "effective_until IS NULL OR effective_until > effective_from",
    ),
    (
        "configuration_unit_revisions",
        "ck_configuration_unit_revisions_configuration_unit_staffing_nonnegative",
        "ck_configuration_unit_revisions_staffing_nonnegative",
        "minimum_managers >= 0 AND minimum_analysts >= 0",
    ),
    (
        "configuration_unit_revisions",
        "ck_configuration_unit_revisions_configuration_unit_staffing_shape",
        "ck_configuration_unit_revisions_staffing_shape",
        "kind = 'TEAM' OR (minimum_managers = 0 AND minimum_analysts = 0)",
    ),
    (
        "maintenance_job_states",
        "ck_maintenance_job_states_maintenance_lease_generation_nonnegative",
        "ck_maintenance_job_states_lease_generation_nonnegative",
        "lease_generation >= 0",
    ),
    (
        "product_upload_intents",
        "ck_product_upload_intents_product_upload_operation_lease_generation_nonnegative",
        "ck_product_upload_intents_lease_generation_nonnegative",
        "operation_lease_generation >= 0",
    ),
)

_POSTGRES_UPGRADE = (
    "ALTER TABLE analytics_export_audit_events RENAME CONSTRAINT "
    "ck_analytics_export_audit_events_analytics_export_event_6d1a TO "
    "ck_analytics_export_audit_events_sequence_positive",
    "ALTER TABLE configuration_hierarchy_edges RENAME CONSTRAINT "
    "ck_configuration_hierarchy_edges_configuration_edge_dis_cabe TO "
    "ck_configuration_hierarchy_edges_distinct_units",
    "ALTER TABLE configuration_hierarchy_edges RENAME CONSTRAINT "
    "ck_configuration_hierarchy_edges_configuration_edge_eff_13fc TO "
    "ck_configuration_hierarchy_edges_effective_window",
    "ALTER TABLE configuration_unit_revisions RENAME CONSTRAINT "
    "ck_configuration_unit_revisions_configuration_unit_effe_79b8 TO "
    "ck_configuration_unit_revisions_effective_window",
    "ALTER TABLE configuration_unit_revisions RENAME CONSTRAINT "
    "ck_configuration_unit_revisions_configuration_unit_staf_bf25 TO "
    "ck_configuration_unit_revisions_staffing_nonnegative",
    "ALTER TABLE configuration_unit_revisions RENAME CONSTRAINT "
    "ck_configuration_unit_revisions_configuration_unit_staf_400d TO "
    "ck_configuration_unit_revisions_staffing_shape",
    "ALTER TABLE maintenance_job_states RENAME CONSTRAINT "
    "ck_maintenance_job_states_maintenance_lease_generation__6020 TO "
    "ck_maintenance_job_states_lease_generation_nonnegative",
    "ALTER TABLE product_upload_intents RENAME CONSTRAINT "
    "ck_product_upload_intents_product_upload_operation_leas_9577 TO "
    "ck_product_upload_intents_lease_generation_nonnegative",
)

_POSTGRES_DOWNGRADE = (
    "ALTER TABLE analytics_export_audit_events RENAME CONSTRAINT "
    "ck_analytics_export_audit_events_sequence_positive TO "
    "ck_analytics_export_audit_events_analytics_export_event_6d1a",
    "ALTER TABLE configuration_hierarchy_edges RENAME CONSTRAINT "
    "ck_configuration_hierarchy_edges_distinct_units TO "
    "ck_configuration_hierarchy_edges_configuration_edge_dis_cabe",
    "ALTER TABLE configuration_hierarchy_edges RENAME CONSTRAINT "
    "ck_configuration_hierarchy_edges_effective_window TO "
    "ck_configuration_hierarchy_edges_configuration_edge_eff_13fc",
    "ALTER TABLE configuration_unit_revisions RENAME CONSTRAINT "
    "ck_configuration_unit_revisions_effective_window TO "
    "ck_configuration_unit_revisions_configuration_unit_effe_79b8",
    "ALTER TABLE configuration_unit_revisions RENAME CONSTRAINT "
    "ck_configuration_unit_revisions_staffing_nonnegative TO "
    "ck_configuration_unit_revisions_configuration_unit_staf_bf25",
    "ALTER TABLE configuration_unit_revisions RENAME CONSTRAINT "
    "ck_configuration_unit_revisions_staffing_shape TO "
    "ck_configuration_unit_revisions_configuration_unit_staf_400d",
    "ALTER TABLE maintenance_job_states RENAME CONSTRAINT "
    "ck_maintenance_job_states_lease_generation_nonnegative TO "
    "ck_maintenance_job_states_maintenance_lease_generation__6020",
    "ALTER TABLE product_upload_intents RENAME CONSTRAINT "
    "ck_product_upload_intents_lease_generation_nonnegative TO "
    "ck_product_upload_intents_product_upload_operation_leas_9577",
)


def _replace_checks(*, forward: bool) -> None:
    for table, old_name, new_name, condition in _CHECKS:
        source, target = (old_name, new_name) if forward else (new_name, old_name)
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(op.f(source), type_="check")
            batch.create_check_constraint(op.f(target), condition)


def _rename_postgres(statements: tuple[str, ...]) -> None:
    for statement in statements:
        op.execute(sa.text(statement))


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        _rename_postgres(_POSTGRES_UPGRADE)
        return
    _replace_checks(forward=True)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        _rename_postgres(_POSTGRES_DOWNGRADE)
        return
    _replace_checks(forward=False)
