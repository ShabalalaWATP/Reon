"""Schema contract for context-namespaced notification preferences."""

from pathlib import Path

from istari_service.action_notification_models import NotificationPreference

MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "0045_notification_preference_contexts.py"
)


def test_notification_preference_context_migration_backfills_and_rekeys() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert '"identity_context"' in source
    assert "WHERE role = 'REQUESTER'" in source
    assert "uq_notification_preferences_user_context_group" in source
    assert '["user_id", "identity_context", "event_group"]' in source
    assert "DELETE FROM notification_preferences" in source


def test_notification_preference_model_has_context_unique_boundary() -> None:
    table = NotificationPreference.__table__
    assert "identity_context" in table.c
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("user_id", "identity_context", "event_group") in unique_columns
