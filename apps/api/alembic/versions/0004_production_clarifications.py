"""Versioned Analyst-to-Customer clarification loop.

Revision ID: 0004_clarifications
Revises: 0003_customer_quality
Create Date: 2026-08-07 03:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_clarifications"
down_revision: str | None = "0003_customer_quality"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_STATUSES = (
    "ROUTING_PENDING",
    "TRIAGE_REVIEW",
    "INFORMATION_REQUIRED",
    "COORDINATION_REVIEW",
    "ON_HOLD",
    "ALLOCATION_REVIEW",
    "DELIVERY_PLANNING",
    "IN_PROGRESS",
    "LEAD_REVIEW",
    "REWORK_REQUIRED",
    "QUALITY_REVIEW",
    "READY_FOR_RELEASE",
    "COMPLETED",
    "CLOSED_NOT_PROGRESSED",
    "CANCELLED",
)
NEW_STATUSES = (*OLD_STATUSES[:8], "CUSTOMER_INFORMATION_REQUIRED", *OLD_STATUSES[8:])


def _status_enum(values: tuple[str, ...], name: str) -> sa.Enum:
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        create_constraint=True,
    )


def upgrade() -> None:
    with op.batch_alter_table("service_requests") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=_status_enum(OLD_STATUSES, "request_status"),
            type_=_status_enum(NEW_STATUSES, "request_status"),
            existing_nullable=False,
            existing_server_default="ROUTING_PENDING",
        )
    with op.batch_alter_table("workflow_tasks") as batch_op:
        batch_op.alter_column(
            "expected_status",
            existing_type=_status_enum(
                OLD_STATUSES,
                "task_expected_request_status",
            ),
            type_=_status_enum(
                NEW_STATUSES,
                "task_expected_request_status",
            ),
            existing_nullable=False,
        )
    with op.batch_alter_table("request_events") as batch_op:
        batch_op.alter_column(
            "prior_status",
            existing_type=_status_enum(OLD_STATUSES, "event_prior_status"),
            type_=_status_enum(NEW_STATUSES, "event_prior_status"),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "next_status",
            existing_type=_status_enum(OLD_STATUSES, "event_next_status"),
            type_=_status_enum(NEW_STATUSES, "event_next_status"),
            existing_nullable=True,
        )
    op.create_table(
        "clarification_threads",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_specialist_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("response_deadline", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "ANSWERED",
                "WITHDRAWN",
                name="clarification_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
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
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.ForeignKeyConstraint(
            ["assigned_specialist_id"],
            ["users.id"],
            name="fk_clarification_threads_assigned_specialist_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["service_requests.id"],
            name="fk_clarification_threads_request_id_service_requests",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name="fk_clarification_threads_requested_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_clarification_threads"),
        sa.UniqueConstraint(
            "request_id",
            "sequence",
            name="uq_clarification_threads_request_id",
        ),
    )
    op.create_index(
        "ix_clarification_threads_request_id",
        "clarification_threads",
        ["request_id"],
    )
    op.create_index(
        "ix_clarification_threads_status",
        "clarification_threads",
        ["status"],
    )
    op.create_index(
        "uq_open_clarification_per_request",
        "clarification_threads",
        ["request_id"],
        unique=True,
        sqlite_where=sa.text("status = 'OPEN'"),
        postgresql_where=sa.text("status = 'OPEN'"),
    )
    op.create_table(
        "clarification_messages",
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "REQUEST",
                "RESPONSE",
                "WITHDRAWAL",
                name="clarification_message_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_clarification_messages_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["clarification_threads.id"],
            name="fk_clarification_messages_thread_id_clarification_threads",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_clarification_messages"),
        sa.CheckConstraint(
            "sequence > 0",
            name="positive_sequence",
        ),
        sa.UniqueConstraint(
            "thread_id",
            "kind",
            name="uq_clarification_messages_thread_kind",
        ),
        sa.UniqueConstraint(
            "thread_id",
            "sequence",
            name="uq_clarification_messages_thread_sequence",
        ),
    )
    op.create_index(
        "ix_clarification_messages_thread_id",
        "clarification_messages",
        ["thread_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_clarification_messages_thread_id",
        table_name="clarification_messages",
    )
    op.drop_table("clarification_messages")
    op.drop_index(
        "uq_open_clarification_per_request",
        table_name="clarification_threads",
    )
    op.drop_index(
        "ix_clarification_threads_status",
        table_name="clarification_threads",
    )
    op.drop_index(
        "ix_clarification_threads_request_id",
        table_name="clarification_threads",
    )
    op.drop_table("clarification_threads")
    with op.batch_alter_table("request_events") as batch_op:
        batch_op.alter_column(
            "prior_status",
            existing_type=_status_enum(NEW_STATUSES, "event_prior_status"),
            type_=_status_enum(OLD_STATUSES, "event_prior_status"),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "next_status",
            existing_type=_status_enum(NEW_STATUSES, "event_next_status"),
            type_=_status_enum(OLD_STATUSES, "event_next_status"),
            existing_nullable=True,
        )
    with op.batch_alter_table("workflow_tasks") as batch_op:
        batch_op.alter_column(
            "expected_status",
            existing_type=_status_enum(
                NEW_STATUSES,
                "task_expected_request_status",
            ),
            type_=_status_enum(
                OLD_STATUSES,
                "task_expected_request_status",
            ),
            existing_nullable=False,
        )
    with op.batch_alter_table("service_requests") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=_status_enum(NEW_STATUSES, "request_status"),
            type_=_status_enum(OLD_STATUSES, "request_status"),
            existing_nullable=False,
            existing_server_default="ROUTING_PENDING",
        )
