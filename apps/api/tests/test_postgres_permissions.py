"""Least-privilege PostgreSQL grant construction tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from istari_service.postgres_permissions import (
    IMMUTABLE_TABLES,
    NON_DELETABLE_TABLES,
    permission_statements,
)


def test_sealing_migration_defines_postgresql_evidence_guards() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/0018_configuration_snapshot_sealing.py"
    )
    contents = migration.read_text(encoding="utf-8")

    assert "guard_configuration_approval_insert" in contents
    assert "guard_configuration_activation_insert" in contents
    assert "NEW.reviewed_version <> candidate.version" in contents
    assert "candidate.version <> evidence.reviewed_version + 2" in contents


def test_legal_hold_migration_seals_attributable_evidence() -> None:
    migration = (
        Path(__file__).parents[1] / "alembic/versions/0041_legal_hold_immutability.py"
    ).read_text(encoding="utf-8")

    assert "BEFORE UPDATE OR DELETE ON legal_holds" in migration
    assert "legal-hold application evidence is immutable" in migration
    assert "legal-hold release evidence must be attributable" in migration


def test_permission_set_grants_runtime_and_read_only_backup_access() -> None:
    statements = permission_statements("istari_runtime", "istari_backup")
    combined = "\n".join(statements)

    assert "CREATE ON SCHEMA public FROM PUBLIC" in combined
    assert "SELECT, INSERT, UPDATE, DELETE" in combined
    assert "SELECT ON ALL TABLES" in combined
    assert "REVOKE UPDATE, DELETE, TRUNCATE" in combined
    assert "istari_runtime" in combined
    assert "istari_backup" in combined
    assert all(table in combined for table in IMMUTABLE_TABLES)
    assert all(table in combined for table in NON_DELETABLE_TABLES)
    assert "security_events" in IMMUTABLE_TABLES
    assert "istari_maintenance" not in combined


def test_permission_set_bounds_configured_maintenance_role() -> None:
    combined = "\n".join(
        permission_statements("istari_runtime", "istari_backup", "istari_maintenance")
    )
    assert "GRANT SELECT ON ALL TABLES" in combined
    assert "GRANT INSERT ON TABLE public.legal_holds" in combined
    assert "GRANT UPDATE (released_at, released_by)" in combined
    assert "GRANT INSERT ON TABLE public.operational_runs" in combined
    assert "public.security_events" in combined
    assert 'admin_audit_events TO "istari_maintenance"' not in combined
    assert "GRANT UPDATE ON ALL TABLES" not in combined
    assert "GRANT UPDATE (username, email, display_name, password_hash" in combined
    assert (
        "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE public.legal_holds"
        in combined
    )


@pytest.mark.parametrize(
    ("runtime", "backup"),
    [
        ("", "backup"),
        ("Runtime", "backup"),
        ("runtime;drop", "backup"),
        ("runtime", 'backup"role'),
    ],
)
def test_permission_set_rejects_untrusted_role_names(runtime: str, backup: str) -> None:
    with pytest.raises(ValueError, match="PostgreSQL role name"):
        permission_statements(runtime, backup)
