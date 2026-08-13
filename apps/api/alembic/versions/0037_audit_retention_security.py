"""Add versioned audit keys, legal holds and security-event evidence."""

import sqlalchemy as sa
from alembic import op

revision: str = "0037_audit_retention_security"
down_revision: str | None = "0036_product_hardening"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("service_requests", sa.Column("audit_anchor_key_id", sa.String(64)))
    op.add_column(
        "request_events",
        sa.Column(
            "audit_key_id", sa.String(64), server_default="legacy", nullable=False
        ),
    )
    op.add_column("admin_audit_anchors", sa.Column("anchor_key_id", sa.String(64)))
    op.add_column(
        "admin_audit_events",
        sa.Column(
            "audit_key_id", sa.String(64), server_default="legacy", nullable=False
        ),
    )
    op.execute(
        "UPDATE service_requests SET audit_anchor_key_id = 'legacy' WHERE audit_event_count > 0"
    )
    op.execute(
        "UPDATE admin_audit_anchors SET anchor_key_id = 'legacy' WHERE event_count > 0"
    )
    op.create_table(
        "security_events",
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("subject_hash", sa.String(64)),
        sa.Column("source_hash", sa.String(64)),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("correlation_id", sa.String(80)),
        sa.Column("request_method", sa.String(10)),
        sa.Column("route_template", sa.String(160)),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "length(event_type) > 0",
            name="ck_security_events_security_event_type_present",
        ),
    )
    op.create_index(
        "ix_security_events_type_created",
        "security_events",
        ["event_type", "created_at"],
    )
    for column in (
        "event_type",
        "outcome",
        "actor_user_id",
        "subject_hash",
        "source_hash",
        "correlation_id",
    ):
        op.create_index(f"ix_security_events_{column}", "security_events", [column])
    op.create_table(
        "legal_holds",
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("authorised_by", sa.String(160), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("released_by", sa.String(160)),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_legal_holds_target_type", "legal_holds", ["target_type"])
    op.create_index("ix_legal_holds_target_id", "legal_holds", ["target_id"])
    op.create_index(
        "uq_legal_holds_active_target",
        "legal_holds",
        ["target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL"),
        sqlite_where=sa.text("released_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("legal_holds")
    op.drop_table("security_events")
    op.drop_column("admin_audit_events", "audit_key_id")
    op.drop_column("admin_audit_anchors", "anchor_key_id")
    op.drop_column("request_events", "audit_key_id")
    op.drop_column("service_requests", "audit_anchor_key_id")
