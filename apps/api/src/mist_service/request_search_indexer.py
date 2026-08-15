"""Asynchronously enrich submitted request projections with local embeddings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.request_embeddings import RequestEmbeddingProvider
from mist_service.request_search_models import (
    EmbeddingState,
    RequestSearchDocument,
)


@dataclass(frozen=True, slots=True)
class PendingSearchDocument:
    request_id: UUID
    document_version: int
    text: str


class RequestSearchIndexer:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        provider: RequestEmbeddingProvider,
        *,
        batch_size: int,
    ) -> None:
        self._sessions = sessions
        self._provider = provider
        self._batch_size = batch_size

    async def reconcile_once(self) -> bool:
        pending = await self._pending_documents()
        if not pending:
            return False
        vectors = await self._provider.embed([item.text for item in pending])
        if len(vectors) != len(pending):
            raise ValueError("embedding model returned the wrong number of vectors")
        await self._store_vectors(pending, vectors)
        return True

    async def _pending_documents(self) -> list[PendingSearchDocument]:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(RequestSearchDocument)
                    .where(
                        RequestSearchDocument.embedding_state == EmbeddingState.PENDING
                    )
                    .order_by(RequestSearchDocument.created_at)
                    .limit(self._batch_size)
                )
            ).scalars()
            return [
                PendingSearchDocument(
                    request_id=row.request_id,
                    document_version=row.document_version,
                    text=row.searchable_text,
                )
                for row in rows
            ]

    async def _store_vectors(
        self,
        pending: Sequence[PendingSearchDocument],
        vectors: Sequence[list[float]],
    ) -> None:
        async with self._sessions() as session, session.begin():
            now = datetime.now(UTC)
            for item, vector in zip(pending, vectors, strict=True):
                document = await session.scalar(
                    select(RequestSearchDocument)
                    .where(
                        RequestSearchDocument.request_id == item.request_id,
                        RequestSearchDocument.document_version == item.document_version,
                        RequestSearchDocument.embedding_state == EmbeddingState.PENDING,
                    )
                    .with_for_update()
                )
                if document is None:
                    continue
                document.embedding = vector
                document.embedding_model = self._provider.model_name
                document.embedding_state = EmbeddingState.READY
                document.indexed_at = now
