"""Harden retention cascading and deployment-role privileges."""

from alembic import op

revision: str = "0039_retention_boundaries"
down_revision: str | None = "0038_request_event_hash_audience"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_clarification_messages_thread_id_clarification_threads",
        "clarification_messages",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_clarification_messages_thread_id_clarification_threads",
        "clarification_messages",
        "clarification_threads",
        ["thread_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_clarification_messages_thread_id_clarification_threads",
        "clarification_messages",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_clarification_messages_thread_id_clarification_threads",
        "clarification_messages",
        "clarification_threads",
        ["thread_id"],
        ["id"],
        ondelete="RESTRICT",
    )
