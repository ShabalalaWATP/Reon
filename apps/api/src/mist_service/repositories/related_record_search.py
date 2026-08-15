"""Indexed candidate retrieval for explainable related-request matching."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    ColumnElement,
    and_,
    cast,
    desc,
    func,
    literal_column,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.domain import Actor
from mist_service.models import Deliverable, DeliverableStatus, ServiceRequest
from mist_service.related_record_scoring import (
    SearchCandidate,
    score_candidates,
    significant_terms,
)
from mist_service.repositories.route_access import route_membership_condition
from mist_service.request_search_models import (
    EMBEDDING_DIMENSIONS,
    EmbeddingState,
    RequestSearchDocument,
)
from mist_service.schemas.related_records import (
    RelatedRecordCandidateList,
    RelatedRecordSearchMode,
)

POOL_LIMIT = 100


class RelatedRecordSearch:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        source_id: UUID,
        actor: Actor,
        *,
        query: str | None,
        limit: int,
    ) -> RelatedRecordCandidateList:
        membership = route_membership_condition(actor)
        if membership is None:
            return RelatedRecordCandidateList(
                mode=RelatedRecordSearchMode.TEXT_ONLY, items=[]
            )
        membership = and_(membership, ServiceRequest.requester_id != actor.id)
        source_row = (
            await self._session.execute(
                select(ServiceRequest, RequestSearchDocument)
                .join(
                    RequestSearchDocument,
                    RequestSearchDocument.request_id == ServiceRequest.id,
                )
                .where(ServiceRequest.id == source_id)
            )
        ).one_or_none()
        if source_row is None:
            return RelatedRecordCandidateList(
                mode=RelatedRecordSearchMode.TEXT_ONLY, items=[]
            )
        source, source_document = source_row
        pool_ids = await self._candidate_ids(
            source,
            source_document,
            membership,
            query=query,
        )
        candidates = await self._load_candidates(pool_ids)
        mode = (
            RelatedRecordSearchMode.HYBRID
            if query is None and source_document.embedding_state is EmbeddingState.READY
            else RelatedRecordSearchMode.TEXT_ONLY
        )
        return RelatedRecordCandidateList(
            mode=mode,
            items=score_candidates(
                source,
                source_document,
                candidates,
                query=query,
                limit=limit,
            ),
        )

    async def _candidate_ids(
        self,
        source: ServiceRequest,
        source_document: RequestSearchDocument,
        membership: ColumnElement[bool],
        *,
        query: str | None,
    ) -> set[UUID]:
        dialect = self._session.bind.dialect.name if self._session.bind else ""
        if dialect != "postgresql":
            return set(
                await self._session.scalars(
                    select(ServiceRequest.id)
                    .where(ServiceRequest.id != source.id, membership)
                    .order_by(ServiceRequest.updated_at.desc())
                    .limit(POOL_LIMIT * 2)
                )
            )
        text = query or " OR ".join(
            significant_terms(source_document.searchable_text, limit=40)
        )
        identifiers = await self._postgres_text_ids(
            source.id, membership, text, query=query
        )
        if query is None and source_document.embedding is not None:
            identifiers.update(
                await self._postgres_vector_ids(
                    source.id, membership, source_document.embedding
                )
            )
        if identifiers:
            return identifiers
        return set(
            await self._session.scalars(
                select(ServiceRequest.id)
                .where(ServiceRequest.id != source.id, membership)
                .order_by(ServiceRequest.updated_at.desc())
                .limit(POOL_LIMIT)
            )
        )

    async def _postgres_text_ids(
        self,
        source_id: UUID,
        membership: ColumnElement[bool],
        text: str,
        *,
        query: str | None,
    ) -> set[UUID]:
        if not text.strip():
            return set()
        search_vector: ColumnElement[Any] = literal_column(
            "request_search_documents.search_vector"
        )
        ts_query = func.websearch_to_tsquery("english", text)
        rank = func.ts_rank_cd(search_vector, ts_query)
        conditions = [search_vector.op("@@")(ts_query)]
        if query:
            conditions.append(
                ServiceRequest.reference.ilike(f"%{_escape_like(query)}%", escape="\\")
            )
        statement = (
            select(ServiceRequest.id)
            .join(
                RequestSearchDocument,
                RequestSearchDocument.request_id == ServiceRequest.id,
            )
            .where(
                ServiceRequest.id != source_id,
                membership,
                or_(*conditions),
            )
            .order_by(desc(rank), ServiceRequest.updated_at.desc())
            .limit(POOL_LIMIT)
        )
        identifiers = set(await self._session.scalars(statement))
        if query:
            similarity = func.similarity(RequestSearchDocument.searchable_text, query)
            identifiers.update(
                await self._session.scalars(
                    select(ServiceRequest.id)
                    .join(
                        RequestSearchDocument,
                        RequestSearchDocument.request_id == ServiceRequest.id,
                    )
                    .where(
                        ServiceRequest.id != source_id,
                        membership,
                        RequestSearchDocument.searchable_text.op("%")(query),
                    )
                    .order_by(desc(similarity))
                    .limit(POOL_LIMIT)
                )
            )
        return identifiers

    async def _postgres_vector_ids(
        self,
        source_id: UUID,
        membership: ColumnElement[bool],
        embedding: list[float],
    ) -> set[UUID]:
        distance = cast(
            RequestSearchDocument.embedding, VECTOR(EMBEDDING_DIMENSIONS)
        ).cosine_distance(embedding)
        return set(
            await self._session.scalars(
                select(ServiceRequest.id)
                .join(
                    RequestSearchDocument,
                    RequestSearchDocument.request_id == ServiceRequest.id,
                )
                .where(
                    ServiceRequest.id != source_id,
                    membership,
                    RequestSearchDocument.embedding_state == EmbeddingState.READY,
                    RequestSearchDocument.embedding.is_not(None),
                )
                .order_by(distance)
                .limit(POOL_LIMIT)
            )
        )

    async def _load_candidates(self, identifiers: set[UUID]) -> list[SearchCandidate]:
        if not identifiers:
            return []
        product_available = (
            select(Deliverable.id)
            .where(
                Deliverable.request_id == ServiceRequest.id,
                Deliverable.status == DeliverableStatus.RELEASED,
                Deliverable.released_at.is_not(None),
            )
            .exists()
        )
        rows = (
            await self._session.execute(
                select(
                    ServiceRequest,
                    RequestSearchDocument,
                    product_available.label("product_available"),
                )
                .join(
                    RequestSearchDocument,
                    RequestSearchDocument.request_id == ServiceRequest.id,
                )
                .where(ServiceRequest.id.in_(identifiers))
            )
        ).all()
        return [
            SearchCandidate(request, document, available)
            for request, document, available in rows
        ]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
