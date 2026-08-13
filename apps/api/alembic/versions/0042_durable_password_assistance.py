"""Durable password-assistance worker state."""

import sqlalchemy as sa
from alembic import op

revision: str = "0042_durable_password_assistance"
down_revision: str | None = "0041_legal_hold_immutability"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "password_assistance_attempts", sa.Column("email_hash", sa.String(64))
    )
    op.add_column(
        "password_assistance_attempts", sa.Column("email_key_id", sa.String(64))
    )
    op.add_column("users", sa.Column("assistance_email_hash", sa.String(64)))
    op.add_column("users", sa.Column("assistance_email_key_id", sa.String(64)))
    op.create_index(
        "ix_users_assistance_email_hash", "users", ["assistance_email_hash"]
    )
    op.add_column(
        "password_assistance_attempts",
        sa.Column(
            "processing_status",
            sa.String(16),
            server_default="COMPLETED",
            nullable=False,
        ),
    )
    op.add_column(
        "password_assistance_attempts",
        sa.Column(
            "processing_attempts", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "password_assistance_attempts",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "password_assistance_attempts",
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_password_assistance_attempts_email_hash",
        "password_assistance_attempts",
        ["email_hash"],
    )
    op.create_index(
        "ix_password_assistance_attempts_processing_status",
        "password_assistance_attempts",
        ["processing_status"],
    )
    op.create_index(
        "ix_password_assistance_attempts_next_attempt_at",
        "password_assistance_attempts",
        ["next_attempt_at"],
    )
    op.alter_column(
        "password_assistance_attempts", "processing_status", server_default="PENDING"
    )


def downgrade() -> None:
    op.drop_index("ix_users_assistance_email_hash", table_name="users")
    op.drop_column("users", "assistance_email_key_id")
    op.drop_column("users", "assistance_email_hash")
    for name in (
        "ix_password_assistance_attempts_next_attempt_at",
        "ix_password_assistance_attempts_processing_status",
        "ix_password_assistance_attempts_email_hash",
    ):
        op.drop_index(name, table_name="password_assistance_attempts")
    for name in (
        "processed_at",
        "next_attempt_at",
        "processing_attempts",
        "processing_status",
        "email_hash",
        "email_key_id",
    ):
        op.drop_column("password_assistance_attempts", name)
