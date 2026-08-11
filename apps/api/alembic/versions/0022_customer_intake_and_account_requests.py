"""Make Customer intake customer-owned and add reviewed account requests.

Revision ID: 0022_customer_intake
Revises: 0021_schema_metadata
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_customer_intake"
down_revision: str | None = "0021_schema_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_FIELDS = (
    ("question_to_answer", sa.Text()),
    ("subject_area_or_location", sa.Text()),
    ("coverage_start", sa.Date()),
    ("coverage_end", sa.Date()),
    ("customer_urgency", sa.String(length=20)),
    ("supported_activity_or_decision", sa.Text()),
    ("constraints_or_caveats", sa.Text()),
    ("supporting_information", sa.Text()),
)


def upgrade() -> None:
    for table in ("service_requests", "request_drafts"):
        with op.batch_alter_table(table) as batch:
            for name, column_type in _NEW_FIELDS:
                batch.add_column(sa.Column(name, column_type, nullable=True))

    op.execute(
        sa.text(
            "UPDATE service_requests SET "
            "question_to_answer = desired_outcome, "
            "subject_area_or_location = requesting_business_area, "
            "coverage_start = required_by, coverage_end = required_by, "
            "customer_urgency = 'ROUTINE', "
            "supported_activity_or_decision = desired_outcome, "
            "constraints_or_caveats = 'No known constraints', "
            "supporting_information = 'No supporting information recorded'"
        )
    )
    with op.batch_alter_table("service_requests") as batch:
        for name, column_type in _NEW_FIELDS:
            batch.alter_column(name, existing_type=column_type, nullable=False)
        batch.drop_column("requesting_business_area")
        batch.drop_column("intended_recipients")
    with op.batch_alter_table("request_drafts") as batch:
        batch.drop_column("requesting_business_area")
        batch.drop_column("intended_recipients")

    op.create_table(
        "account_requests",
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("contact_email", sa.String(length=254), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "APPROVED",
                "REJECTED",
                name="account_request_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_user_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
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
        sa.ForeignKeyConstraint(["created_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_account_requests_contact_email"),
        "account_requests",
        ["contact_email"],
        unique=True,
    )
    op.create_index(
        op.f("ix_account_requests_created_user_id"),
        "account_requests",
        ["created_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_account_requests_reviewed_by_user_id"),
        "account_requests",
        ["reviewed_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_account_requests_status"), "account_requests", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_account_requests_status"), table_name="account_requests")
    op.drop_index(
        op.f("ix_account_requests_reviewed_by_user_id"), table_name="account_requests"
    )
    op.drop_index(
        op.f("ix_account_requests_created_user_id"), table_name="account_requests"
    )
    op.drop_index(
        op.f("ix_account_requests_contact_email"), table_name="account_requests"
    )
    op.drop_table("account_requests")
    for table in ("service_requests", "request_drafts"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column(
                    "requesting_business_area", sa.String(length=120), nullable=True
                )
            )
            batch.add_column(sa.Column("intended_recipients", sa.JSON(), nullable=True))
    legacy_requests = sa.table(
        "service_requests",
        sa.column("requesting_business_area", sa.String(length=120)),
        sa.column("intended_recipients", sa.JSON()),
        sa.column("subject_area_or_location", sa.Text()),
    )
    op.execute(
        sa.update(legacy_requests).values(
            requesting_business_area=legacy_requests.c.subject_area_or_location,
            intended_recipients=[],
        )
    )
    with op.batch_alter_table("service_requests") as batch:
        batch.alter_column(
            "requesting_business_area",
            existing_type=sa.String(length=120),
            nullable=False,
        )
        batch.alter_column(
            "intended_recipients", existing_type=sa.JSON(), nullable=False
        )
    for table in ("service_requests", "request_drafts"):
        with op.batch_alter_table(table) as batch:
            for name, _column_type in reversed(_NEW_FIELDS):
                batch.drop_column(name)
