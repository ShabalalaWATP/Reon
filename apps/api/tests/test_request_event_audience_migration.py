"""Historical request-event audience migration contract."""

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1] / "alembic/versions/0035_request_event_audience.py"
)
STAFF_DEFAULT_MIGRATION = (
    Path(__file__).parents[1] / "alembic/versions/0040_request_event_staff_default.py"
)


def test_migration_backfills_every_historical_staff_only_event() -> None:
    contents = MIGRATION.read_text(encoding="utf-8")
    assert "details ->> 'audience'" in contents
    assert "json_extract(details, '$.audience')" in contents
    assert "CURRENT_OWNER" in contents
    assert "OWNERSHIP_RETURN_REQUESTED" in contents
    assert "workflow_claimed" in contents
    assert "workflow_recovery_queued" in contents
    assert "related_record_linked" in contents
    assert "task_hastener" not in contents


def test_migration_downgrade_only_removes_the_enforcement_column() -> None:
    contents = MIGRATION.read_text(encoding="utf-8")
    downgrade = contents.split("def downgrade() -> None:", maxsplit=1)[1]
    assert "DELETE FROM request_events" not in downgrade
    assert 'drop_column("request_events", "audience")' in downgrade


def test_staff_default_migration_backfills_historical_internal_events() -> None:
    contents = STAFF_DEFAULT_MIGRATION.read_text(encoding="utf-8")
    for event_type in (
        "task_hastener",
        "workflow_assign",
        "workflow_send_to_allocation",
        "workflow_resume",
        "workflow_close",
        "workflow_request_information",
        "workflow_provide_information",
        "workflow_request_clarification",
        "workflow_provide_clarification",
        "workflow_withdraw",
        "workflow_hold",
        "workflow_return_to_triage",
        "workflow_return_to_coordination",
        "workflow_return_for_reallocation",
        "workflow_changes_required",
        "PRODUCT_SUBMITTED",
        "MANAGER_REVIEW_APPROVED",
        "PRODUCT_APPROVED",
        "PRODUCT_REWORK_REQUESTED",
    ):
        assert event_type in contents
    assert "hash_version = 1" in contents
    assert 'server_default="STAFF_ONLY"' in contents
