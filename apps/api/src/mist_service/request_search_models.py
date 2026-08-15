"""Persistence model for the searchable service-request projection."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text, func
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, TypeEngine

from mist_service.models import UTC_TS, UUID_TYPE, Base, _enum

EMBEDDING_DIMENSIONS = 384
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
SEARCH_PROJECTION_VERSION = 1


class EmbeddingState(StrEnum):
    PENDING = "PENDING"
    READY = "READY"


class SemanticVector(TypeDecorator[list[float]]):
    """Use pgvector in PostgreSQL and portable JSON in SQLite tests."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(VECTOR(EMBEDDING_DIMENSIONS))
        return dialect.type_descriptor(JSON())


class RequestSearchDocument(Base):
    __tablename__ = "request_search_documents"
    __table_args__ = (
        CheckConstraint("document_version > 0", name="positive_document_version"),
    )

    request_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("service_requests.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    document_version: Mapped[int] = mapped_column(Integer)
    title_text: Mapped[str] = mapped_column(Text)
    question_text: Mapped[str] = mapped_column(Text)
    outcome_text: Mapped[str] = mapped_column(Text)
    context_text: Mapped[str] = mapped_column(Text)
    searchable_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(SemanticVector())
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    embedding_state: Mapped[EmbeddingState] = mapped_column(
        _enum(EmbeddingState, "request_embedding_state"),
        default=EmbeddingState.PENDING,
        server_default=EmbeddingState.PENDING,
        index=True,
    )
    indexed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    created_at: Mapped[datetime] = mapped_column(UTC_TS, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTC_TS,
        server_default=func.now(),
        onupdate=func.now(),
    )
