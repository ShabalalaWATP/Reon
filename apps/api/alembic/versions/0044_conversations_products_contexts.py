"""Add structured conversations, managed-product mode and session contexts.

Revision ID: 0044_context_conversations
Revises: 0043_security_event_dedup
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_context_conversations"
down_revision: str | None = "0043_security_event_dedup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QC_TEAM_ID = "d2893c1e-7018-5102-bacc-f4b1217721e3"
QC_BACKFILL_REASON = "0044 Combined QC Team membership backfill."


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "customer_context_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE users SET customer_context_enabled = true "
        "WHERE role IN ('INTAKE_TRIAGE', 'SERVICE_COORDINATION', "
        "'OPERATIONS_ALLOCATION', 'DELIVERY_TEAM_LEAD', "
        "'DELIVERY_SPECIALIST', 'QUALITY_RELEASE')"
    )
    op.add_column(
        "sessions",
        sa.Column(
            "active_context",
            sa.Enum(
                "CUSTOMER",
                "STAFF",
                name="identity_context",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="STAFF",
            nullable=False,
        ),
    )
    op.add_column(
        "sessions",
        sa.Column("context_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.execute(
        "UPDATE sessions SET active_context = 'CUSTOMER' "
        "WHERE user_id IN (SELECT id FROM users WHERE role = 'REQUESTER')"
    )
    op.add_column(
        "service_requests",
        sa.Column(
            "product_mode",
            sa.Enum(
                "LEGACY",
                "MANAGED",
                name="request_product_mode",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="LEGACY",
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE service_requests SET product_mode = 'MANAGED' "
        "WHERE EXISTS (SELECT 1 FROM product_packages "
        "WHERE product_packages.request_id = service_requests.id)"
    )
    op.add_column("product_packages", sa.Column("covering_note", sa.Text()))
    _backfill_qc_team()
    _create_conversation_tables()


def _backfill_qc_team() -> None:
    op.execute(
        sa.text(
            "INSERT INTO organisation_units ("
            "id, code, name, kind, parent_id, staffing_status, "
            "routing_candidate_group, manager_candidate_group, "
            "analyst_candidate_group, sort_order, is_configured, version, "
            "created_at, updated_at"
            ") SELECT "
            "CAST('d2893c1e-7018-5102-bacc-f4b1217721e3' AS UUID), "
            "'QC_TEAM', 'Combined QC Team', "
            "'TEAM', parent.id, 'STAFFED', NULL, 'qc-team-managers', "
            "'qc-team-members', 1000, false, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
            "FROM organisation_units parent WHERE parent.code = 'CRIOC' "
            "ON CONFLICT (id) DO UPDATE SET "
            "code = EXCLUDED.code, name = EXCLUDED.name, kind = EXCLUDED.kind, "
            "parent_id = EXCLUDED.parent_id, staffing_status = EXCLUDED.staffing_status, "
            "routing_candidate_group = NULL, "
            "manager_candidate_group = EXCLUDED.manager_candidate_group, "
            "analyst_candidate_group = EXCLUDED.analyst_candidate_group, "
            "is_configured = false"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO user_organisation_memberships ("
            "id, user_id, unit_id, created_at"
            ") SELECT "
            "CAST(md5(CAST(u.id AS TEXT) || :qc_projection_suffix) AS UUID), "
            "u.id, CAST('d2893c1e-7018-5102-bacc-f4b1217721e3' AS UUID), "
            "CURRENT_TIMESTAMP "
            "FROM users u WHERE u.role = 'QUALITY_RELEASE' AND u.is_active = true "
            "AND NOT EXISTS (SELECT 1 FROM user_organisation_memberships m "
            "WHERE m.user_id = u.id "
            "AND m.unit_id = "
            "CAST('d2893c1e-7018-5102-bacc-f4b1217721e3' AS UUID))"
        ).bindparams(qc_projection_suffix=":0044-qc-projection")
    )
    op.execute(
        sa.text(
            "INSERT INTO team_memberships ("
            "id, user_id, team_id, workspace_position, effective_from, "
            "effective_until, start_projected_at, end_projected_at, "
            "started_by_user_id, start_reason, ended_by_user_id, end_reason, "
            "version, created_at, updated_at"
            ") SELECT "
            "CAST(md5(CAST(u.id AS TEXT) || :qc_membership_suffix) AS UUID), "
            "u.id, CAST('d2893c1e-7018-5102-bacc-f4b1217721e3' AS UUID), "
            "'MANAGER', CURRENT_TIMESTAMP, "
            "NULL, CURRENT_TIMESTAMP, NULL, NULL, "
            "'0044 Combined QC Team membership backfill.', NULL, NULL, 1, "
            "CURRENT_TIMESTAMP, "
            "CURRENT_TIMESTAMP FROM users u "
            "WHERE u.role = 'QUALITY_RELEASE' AND u.is_active = true "
            "AND NOT EXISTS (SELECT 1 FROM team_memberships tm "
            "WHERE tm.user_id = u.id "
            "AND tm.team_id = "
            "CAST('d2893c1e-7018-5102-bacc-f4b1217721e3' AS UUID) "
            "AND tm.effective_until IS NULL)"
        ).bindparams(qc_membership_suffix=":0044-qc-membership")
    )


def _create_conversation_tables() -> None:
    op.create_table(
        "request_conversations",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("opened_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "target_type",
            sa.Enum(
                "CUSTOMER",
                "CURRENT_OWNER",
                "TEAM_MANAGERS",
                "ASSIGNED_ANALYSTS",
                "ROUTE_UNIT",
                "QC_TEAM",
                name="conversation_target_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("target_unit_id", sa.Uuid()),
        sa.Column("target_label", sa.String(160), nullable=False),
        sa.Column("subject", sa.String(160), nullable=False),
        sa.Column(
            "visibility",
            sa.Enum(
                "CUSTOMER_AND_STAFF",
                "STAFF_ONLY",
                name="conversation_visibility",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["opened_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_unit_id"], ["organisation_units.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "request_id",
        "opened_by_user_id",
        "target_type",
        "target_unit_id",
        "visibility",
    ):
        op.create_index(
            op.f(f"ix_request_conversations_{column}"),
            "request_conversations",
            [column],
        )
    op.create_index(
        "ix_request_conversations_request_created",
        "request_conversations",
        ["request_id", "created_at", "id"],
    )
    op.create_table(
        "request_conversation_messages",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "sender_role",
            sa.Enum(
                "PLATFORM_ADMIN",
                "REQUESTER",
                "INTAKE_TRIAGE",
                "SERVICE_COORDINATION",
                "OPERATIONS_ALLOCATION",
                "DELIVERY_TEAM_LEAD",
                "DELIVERY_SPECIALIST",
                "QUALITY_RELEASE",
                name="conversation_sender_role",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_sha256", sa.String(64), nullable=False),
        sa.Column("reply_to_message_id", sa.Uuid()),
        sa.Column("client_mutation_id", sa.Uuid(), nullable=False),
        sa.Column("request_event_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["request_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reply_to_message_id"],
            ["request_conversation_messages.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_event_id"], ["request_events.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sender_user_id",
            "client_mutation_id",
            name="uq_conversation_message_sender_mutation",
        ),
        sa.UniqueConstraint(
            "request_event_id",
            name=op.f("uq_request_conversation_messages_request_event_id"),
        ),
    )
    for column in ("conversation_id", "sender_user_id", "client_mutation_id"):
        op.create_index(
            op.f(f"ix_request_conversation_messages_{column}"),
            "request_conversation_messages",
            [column],
        )
    op.create_index(
        "ix_conversation_messages_conversation_created",
        "request_conversation_messages",
        ["conversation_id", "created_at", "id"],
    )
    op.create_table(
        "request_conversation_deliveries",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["request_conversation_messages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "recipient_user_id",
            name="uq_conversation_delivery_recipient",
        ),
    )
    op.create_index(
        op.f("ix_request_conversation_deliveries_message_id"),
        "request_conversation_deliveries",
        ["message_id"],
    )
    op.create_index(
        op.f("ix_request_conversation_deliveries_recipient_user_id"),
        "request_conversation_deliveries",
        ["recipient_user_id"],
    )
    op.create_index(
        "ix_conversation_deliveries_recipient_read",
        "request_conversation_deliveries",
        ["recipient_user_id", "read_at"],
    )
    op.execute(
        """
        CREATE FUNCTION protect_conversation_delivery() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'conversation delivery evidence cannot be deleted';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
               OR NEW.message_id IS DISTINCT FROM OLD.message_id
               OR NEW.recipient_user_id IS DISTINCT FROM OLD.recipient_user_id
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR OLD.read_at IS NOT NULL
               OR NEW.read_at IS NULL THEN
                RAISE EXCEPTION 'conversation delivery may only record its first read';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_protect_conversation_delivery
        BEFORE UPDATE OR DELETE ON request_conversation_deliveries
        FOR EACH ROW EXECUTE FUNCTION protect_conversation_delivery()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_protect_conversation_delivery "
        "ON request_conversation_deliveries"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_conversation_delivery()")
    op.drop_table("request_conversation_deliveries")
    op.drop_table("request_conversation_messages")
    op.drop_table("request_conversations")
    op.drop_column("product_packages", "covering_note")
    op.drop_column("service_requests", "product_mode")
    op.drop_column("sessions", "context_version")
    op.drop_column("sessions", "active_context")
    op.drop_column("users", "customer_context_enabled")
    _remove_qc_backfill()


def _remove_qc_backfill() -> None:
    op.execute(
        sa.text(
            "DELETE FROM team_memberships "
            "WHERE team_id = "
            "CAST('d2893c1e-7018-5102-bacc-f4b1217721e3' AS UUID) "
            "AND start_reason = '0044 Combined QC Team membership backfill.' "
            "AND started_by_user_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM user_organisation_memberships "
            "WHERE unit_id = "
            "CAST('d2893c1e-7018-5102-bacc-f4b1217721e3' AS UUID) "
            "AND id = CAST(md5(CAST(user_id AS TEXT) || "
            ":qc_projection_suffix) AS UUID)"
        ).bindparams(qc_projection_suffix=":0044-qc-projection")
    )
    # Retain the compatible unit row because later operational records may
    # reference it. Deleting a shared organisation object is not a safe downgrade.
