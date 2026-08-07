"""Private managed-product metadata and dissemination evidence.

Revision ID: 0013_product_artifacts
Revises: 0012_action_notifications
Create Date: 2026-08-07 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_product_artifacts"
down_revision: str | None = "0012_action_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_packages",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("package_version", sa.Integer(), nullable=False),
        sa.Column("creation_key", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            _enum(
                "DRAFT",
                "REVIEW_READY",
                "MANAGER_APPROVED",
                "DISSEMINATED",
                "REPLACED",
                "WITHDRAWN",
                name="product_package_status",
            ),
            nullable=False,
        ),
        sa.Column("package_checksum", sa.String(64)),
        sa.Column("manager_approved_by_user_id", sa.Uuid()),
        sa.Column("manager_approved_at", _timestamp()),
        sa.Column("disseminated_by_user_id", sa.Uuid()),
        sa.Column("disseminated_at", _timestamp()),
        sa.Column("withdrawn_at", _timestamp()),
        sa.Column("withdrawal_reason", sa.Text()),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_identity_timestamps(updated=True),
        sa.CheckConstraint("package_version > 0", name="product_package_version"),
        sa.CheckConstraint("version > 0", name="product_package_record_version"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_requests.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["manager_approved_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["disseminated_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "package_version"),
        sa.UniqueConstraint("creation_key"),
    )
    _indexes("product_packages", "request_id", "author_user_id", "status")

    op.create_table(
        "product_artefacts",
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("creation_key", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            _enum("MANAGED_FILE", "EXTERNAL_LINK", name="product_artefact_kind"),
            nullable=False,
        ),
        sa.Column(
            "lifecycle",
            _enum(
                "PENDING_UPLOAD",
                "QUARANTINED",
                "CLEAN",
                "RELEASED",
                "FAILED",
                "REPLACED",
                "WITHDRAWN",
                "EXPIRED",
                name="product_artefact_lifecycle",
            ),
            nullable=False,
        ),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("filename", sa.String(180)),
        sa.Column("media_type", sa.String(120)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("checksum", sa.String(64)),
        sa.Column("quarantine_key", sa.String(255)),
        sa.Column("released_key", sa.String(255)),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_identity_timestamps(updated=True),
        sa.CheckConstraint(
            "position BETWEEN 1 AND 10", name="product_artefact_position"
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes > 0", name="product_artefact_size"
        ),
        sa.ForeignKeyConstraint(
            ["package_id"], ["product_packages.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package_id", "position"),
        sa.UniqueConstraint("creation_key"),
        sa.UniqueConstraint("quarantine_key"),
        sa.UniqueConstraint("released_key"),
    )
    _indexes("product_artefacts", "package_id", "lifecycle")

    op.create_table(
        "product_upload_intents",
        sa.Column("artefact_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expected_size_bytes", sa.Integer(), nullable=False),
        sa.Column("expected_media_type", sa.String(120), nullable=False),
        sa.Column("expected_checksum", sa.String(64), nullable=False),
        sa.Column("expires_at", _timestamp(), nullable=False),
        sa.Column("uploaded_at", _timestamp()),
        sa.Column("consumed_at", _timestamp()),
        *_identity_timestamps(),
        sa.ForeignKeyConstraint(
            ["artefact_id"], ["product_artefacts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artefact_id", "idempotency_key"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint("token_hash"),
    )
    _indexes("product_upload_intents", "artefact_id", "expires_at")

    op.create_table(
        "product_scans",
        sa.Column("artefact_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column(
            "result",
            _enum(
                "CLEAN", "FAILED", "UNKNOWN", "TIMED_OUT", name="product_scan_result"
            ),
            nullable=False,
        ),
        sa.Column("scanner", sa.String(80), nullable=False),
        sa.Column("scanner_version", sa.String(40), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(80)),
        sa.Column("findings", sa.JSON(), nullable=False),
        *_identity_timestamps(),
        sa.ForeignKeyConstraint(
            ["artefact_id"], ["product_artefacts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artefact_id", "idempotency_key"),
    )
    _indexes("product_scans", "artefact_id", "result")

    op.create_table(
        "external_product_links",
        sa.Column("artefact_id", sa.Uuid(), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("normalised_domain", sa.String(253), nullable=False),
        sa.Column("expires_at", _timestamp()),
        sa.Column("approved_by_user_id", sa.Uuid()),
        sa.Column("approved_at", _timestamp()),
        sa.Column(
            "qc_attested",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        *_identity_timestamps(),
        sa.ForeignKeyConstraint(
            ["artefact_id"], ["product_artefacts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artefact_id"),
    )
    _indexes("external_product_links", "normalised_domain")

    op.create_table(
        "product_disseminations",
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("disseminated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("package_checksum", sa.String(64), nullable=False),
        sa.Column("withdrawn_at", _timestamp()),
        *_identity_timestamps(),
        sa.ForeignKeyConstraint(
            ["package_id"], ["product_packages.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["disseminated_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package_id", "recipient_user_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    _indexes("product_disseminations", "package_id", "recipient_user_id")

    op.create_table(
        "product_access_events",
        sa.Column("request_id", sa.Uuid()),
        sa.Column("package_id", sa.Uuid()),
        sa.Column("artefact_id", sa.Uuid()),
        sa.Column("target_hash", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            _enum("DOWNLOAD", "REDIRECT", name="product_access_kind"),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            _enum("ALLOWED", "DENIED", "UNAVAILABLE", name="product_access_outcome"),
            nullable=False,
        ),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("correlation_id", sa.String(80)),
        *_identity_timestamps(),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_requests.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["package_id"], ["product_packages.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["artefact_id"], ["product_artefacts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "product_access_events",
        "request_id",
        "package_id",
        "artefact_id",
        "target_hash",
        "actor_user_id",
        "outcome",
    )
    op.create_index(
        "ix_product_access_events_artefact_created",
        "product_access_events",
        ["artefact_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("product_access_events")
    op.drop_table("product_disseminations")
    op.drop_table("external_product_links")
    op.drop_table("product_scans")
    op.drop_table("product_upload_intents")
    op.drop_table("product_artefacts")
    op.drop_table("product_packages")


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _timestamp() -> sa.DateTime:
    return sa.DateTime(timezone=True)


def _identity_timestamps(*, updated: bool = False) -> tuple[sa.Column, ...]:
    columns = [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", _timestamp(), server_default=sa.func.now(), nullable=False
        ),
    ]
    if updated:
        columns.append(
            sa.Column(
                "updated_at", _timestamp(), server_default=sa.func.now(), nullable=False
            )
        )
    return tuple(columns)


def _indexes(table: str, *columns: str) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])
