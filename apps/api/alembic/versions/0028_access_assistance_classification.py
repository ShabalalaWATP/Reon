"""Add managed emails, access assistance and the global classification.

Revision ID: 0028_access_classification
Revises: 0027_workspace_collaboration
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0028_access_classification"
down_revision: str | None = "0027_workspace_collaboration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CLASSIFICATION_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email", sa.String(length=254)))
    op.execute(
        sa.text("UPDATE users SET email = lower(username) || '@istari.example.test'")
    )
    with op.batch_alter_table("users") as batch:
        batch.alter_column("email", existing_type=sa.String(length=254), nullable=False)
        batch.create_index("ix_users_email", ["email"], unique=True)

    op.create_table(
        "platform_classification_settings",
        sa.Column(
            "classification",
            sa.Enum(
                "OFFICIAL",
                "OFFICIAL-SENSITIVE",
                "SECRET",
                "TOP-SECRET",
                name="platform_classification",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid()),
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
        sa.CheckConstraint(
            "version > 0",
            name=op.f(
                "ck_platform_classification_settings_platform_classification_version"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO platform_classification_settings "
            "(id, classification, version) "
            "VALUES (:id, 'OFFICIAL', 1)"
        ).bindparams(sa.bindparam("id", value=UUID(CLASSIFICATION_ID), type_=sa.Uuid()))
    )

    op.create_table(
        "password_assistance_attempts",
        sa.Column("source_key", sa.String(length=72), nullable=False),
        sa.Column("matched_user_id", sa.Uuid()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["matched_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_password_assistance_source_created",
        "password_assistance_attempts",
        ["source_key", "created_at"],
    )
    op.create_index(
        "ix_password_assistance_user_created",
        "password_assistance_attempts",
        ["matched_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("password_assistance_attempts")
    op.drop_table("platform_classification_settings")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_email")
        batch.drop_column("email")
