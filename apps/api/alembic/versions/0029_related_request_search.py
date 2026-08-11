"""Add explainable full-request search and the not-relevant judgement.

Revision ID: 0029_related_request_search
Revises: 0028_access_classification
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import TSVECTOR

revision: str = "0029_related_request_search"
down_revision: str | None = "0028_access_classification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LINK_TYPES = (
    "POSSIBLE_DUPLICATE",
    "RELATED_REQUEST",
    "EXISTING_OUTPUT",
    "NOT_RELEVANT",
)
ORIGINAL_LINK_TYPES = LINK_TYPES[:-1]


def _replace_link_type_check(values: tuple[str, ...]) -> None:
    quoted = ", ".join(f"'{value}'" for value in values)
    with op.batch_alter_table("request_links") as batch:
        batch.drop_constraint(op.f("ck_request_links_request_link_type"), type_="check")
        batch.create_check_constraint("request_link_type", f"link_type IN ({quoted})")


def _backfill_search_documents() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO request_search_documents (
                request_id, document_version, title_text, question_text,
                outcome_text, context_text, searchable_text, embedding_state
            )
            SELECT
                id, 1, title, question_to_answer, desired_outcome,
                background_context || :newline || subject_area_or_location,
                'Title: ' || title || :newline ||
                'Description: ' || description || :newline ||
                'Question to answer: ' || question_to_answer || :newline ||
                'Desired outcome: ' || desired_outcome || :newline ||
                'Background context: ' || background_context || :newline ||
                'Subject area or location: ' || subject_area_or_location || :newline ||
                'Coverage start: ' || CAST(coverage_start AS TEXT) || :newline ||
                'Coverage end: ' || CAST(coverage_end AS TEXT) || :newline ||
                'Customer urgency: ' || customer_urgency || :newline ||
                'Supported activity or decision: ' ||
                    supported_activity_or_decision || :newline ||
                'Required by: ' || CAST(required_by AS TEXT) || :newline ||
                'Required-by reason: ' || required_by_reason || :newline ||
                'Preferred deliverable type: ' ||
                    preferred_deliverable_type || :newline ||
                'Success criteria: ' || success_criteria || :newline ||
                'Constraints or caveats: ' || constraints_or_caveats || :newline ||
                'Supporting information: ' || supporting_information || :newline ||
                'Sensitivity: ' || sensitivity || :newline ||
                'Handling instructions: ' || handling_instructions,
                'PENDING'
            FROM service_requests
            """
        ).bindparams(newline="\n")
    )


def upgrade() -> None:
    connection = op.get_bind()
    is_postgres = connection.dialect.name == "postgresql"
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    embedding_type: sa.types.TypeEngine[object] = (
        VECTOR(384) if is_postgres else sa.JSON()
    )
    op.create_table(
        "request_search_documents",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("title_text", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("outcome_text", sa.Text(), nullable=False),
        sa.Column("context_text", sa.Text(), nullable=False),
        sa.Column("searchable_text", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type),
        sa.Column("embedding_model", sa.String(120)),
        sa.Column(
            "embedding_state",
            sa.Enum(
                "PENDING",
                "READY",
                name="request_embedding_state",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("indexed_at", sa.DateTime(timezone=True)),
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
        sa.CheckConstraint("document_version > 0", name="positive_document_version"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["service_requests.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("request_id"),
    )
    op.create_index(
        "ix_request_search_documents_embedding_state",
        "request_search_documents",
        ["embedding_state"],
    )
    _backfill_search_documents()

    if is_postgres:
        op.add_column(
            "request_search_documents",
            sa.Column(
                "search_vector",
                TSVECTOR(),
                sa.Computed(
                    "setweight(to_tsvector('english'::regconfig, title_text), 'A') || "
                    "setweight(to_tsvector('english'::regconfig, question_text), 'A') || "
                    "setweight(to_tsvector('english'::regconfig, outcome_text), 'B') || "
                    "setweight(to_tsvector('english'::regconfig, context_text), 'C') || "
                    "setweight(to_tsvector('english'::regconfig, searchable_text), 'D')",
                    persisted=True,
                ),
            ),
        )
        op.execute(
            "CREATE INDEX ix_request_search_documents_search_vector "
            "ON request_search_documents USING gin (search_vector)"
        )
        op.execute(
            "CREATE INDEX ix_request_search_documents_trigram "
            "ON request_search_documents USING gin (searchable_text gin_trgm_ops)"
        )
        op.execute(
            "CREATE INDEX ix_request_search_documents_embedding_hnsw "
            "ON request_search_documents USING hnsw (embedding vector_cosine_ops) "
            "WHERE embedding IS NOT NULL"
        )

    _replace_link_type_check(LINK_TYPES)


def downgrade() -> None:
    _replace_link_type_check(ORIGINAL_LINK_TYPES)
    op.drop_table("request_search_documents")
