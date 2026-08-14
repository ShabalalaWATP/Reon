"""Regression checks for migration-owned objects represented in metadata."""

from __future__ import annotations

from istari_service.model_registry import Base


def test_migration_owned_indexes_are_present_in_model_metadata() -> None:
    expected = {
        "request_analytics_facts": {"ix_analytics_team_request"},
        "work_packages": {"ix_work_packages_team_updated_id"},
        "workflow_outbox": {"ix_workflow_outbox_dispatch"},
    }

    for table_name, required_indexes in expected.items():
        actual = {index.name for index in Base.metadata.tables[table_name].indexes}
        assert required_indexes <= actual


def test_long_check_constraints_have_stable_readable_names() -> None:
    expected = {
        "analytics_export_audit_events": {
            "ck_analytics_export_audit_events_sequence_positive"
        },
        "configuration_hierarchy_edges": {
            "ck_configuration_hierarchy_edges_distinct_units",
            "ck_configuration_hierarchy_edges_effective_window",
        },
        "configuration_unit_revisions": {
            "ck_configuration_unit_revisions_effective_window",
            "ck_configuration_unit_revisions_staffing_nonnegative",
            "ck_configuration_unit_revisions_staffing_shape",
        },
        "maintenance_job_states": {
            "ck_maintenance_job_states_lease_generation_nonnegative"
        },
        "product_upload_intents": {
            "ck_product_upload_intents_lease_generation_nonnegative"
        },
    }

    for table_name, required_constraints in expected.items():
        actual = {
            constraint.name
            for constraint in Base.metadata.tables[table_name].constraints
        }
        assert required_constraints <= actual
