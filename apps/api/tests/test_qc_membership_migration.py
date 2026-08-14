"""Upgrade contract for introducing exact Combined QC Team membership."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


def _migration() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/0044_conversations_products_contexts.py"
    )
    specification = spec_from_file_location("qc_membership_migration", path)
    assert specification is not None and specification.loader is not None
    migration = module_from_spec(specification)
    specification.loader.exec_module(migration)
    return migration


def test_upgrade_backfills_active_qc_accounts_as_exact_team_managers(
    monkeypatch,
) -> None:
    migration = _migration()
    statements: list[str] = []
    monkeypatch.setattr(
        migration.op, "execute", lambda value: statements.append(str(value))
    )

    migration._backfill_qc_team()

    combined = " ".join(statements)
    assert migration.QC_TEAM_ID in combined
    assert "'QC_TEAM', 'Combined QC Team'" in combined
    assert "u.role = 'QUALITY_RELEASE' AND u.is_active = true" in combined
    assert "workspace_position" in combined and "'MANAGER'" in combined
    assert "tm.effective_until IS NULL" in combined


def test_downgrade_removes_only_migration_owned_qc_rows(monkeypatch) -> None:
    migration = _migration()
    statements = []
    monkeypatch.setattr(migration.op, "execute", lambda value: statements.append(value))

    migration._remove_qc_backfill()

    combined = " ".join(str(statement) for statement in statements)
    assert migration.QC_BACKFILL_REASON in combined
    assert any(
        statement.compile().params.get("qc_projection_suffix") == ":0044-qc-projection"
        for statement in statements
    )
    assert "DELETE FROM organisation_units" not in combined


def test_qc_backfill_uuid_suffixes_are_bound_parameters(monkeypatch) -> None:
    migration = _migration()
    statements = []
    monkeypatch.setattr(migration.op, "execute", lambda value: statements.append(value))

    migration._backfill_qc_team()

    parameters = [statement.compile().params for statement in statements]
    assert {value for item in parameters for value in item.values()} >= {
        ":0044-qc-projection",
        ":0044-qc-membership",
    }
