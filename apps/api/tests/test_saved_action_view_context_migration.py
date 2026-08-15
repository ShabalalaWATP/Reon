"""Schema contract for context-namespaced saved action views."""

from pathlib import Path

from mist_service.action_notification_models import SavedActionView

MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "0047_saved_action_view_contexts.py"
)


def test_saved_action_view_migration_preserves_staff_views_and_rekeys() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'server_default="STAFF"' in source
    assert "uq_saved_action_views_owner_context_name" in source
    assert '["owner_user_id", "identity_context", "name"]' in source
    assert "DELETE FROM saved_action_views" in source


def test_saved_action_view_model_has_context_unique_boundary() -> None:
    table = SavedActionView.__table__
    assert "identity_context" in table.c
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("owner_user_id", "identity_context", "name") in unique_columns
