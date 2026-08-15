"""Search projection, local embeddings and ranking assurance."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any, ClassVar, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import ApiHarness, request_payload
from mist_service.domain import Actor
from mist_service.models import ServiceRequest, UserRole
from mist_service.related_record_scoring import (
    FIELD_WEIGHTS,
    SearchCandidate,
    _match_band,
    score_candidates,
    significant_terms,
)
from mist_service.repositories.related_record_search import RelatedRecordSearch
from mist_service.request_embeddings import FastEmbedRequestEmbeddingProvider
from mist_service.request_search_indexer import (
    PendingSearchDocument,
    RequestSearchIndexer,
)
from mist_service.request_search_models import (
    EMBEDDING_DIMENSIONS,
    EmbeddingState,
    RequestSearchDocument,
)
from mist_service.request_search_text import MAX_SEARCH_TEXT_CHARACTERS
from mist_service.schemas.related_records import RelatedRecordMatchBand


class StubProvider:
    model_name = "synthetic/local-model"

    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return self.vectors


async def submit(harness: ApiHarness, title: str) -> dict[str, Any]:
    await harness.login("admin2")
    response = await harness.client.post(
        "/api/v1/requests",
        json=request_payload(title=title),
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 201, response.text
    assert await harness.dispatch_start()
    return response.json()


async def test_submission_creates_complete_projection_and_indexer_enriches_it(
    api_harness: ApiHarness,
) -> None:
    assert MAX_SEARCH_TEXT_CHARACTERS >= 27_000
    created = await submit(api_harness, "A complete searchable projection")
    request_id = UUID(created["id"])
    async with api_harness.sessions() as session:
        document = await session.get(RequestSearchDocument, request_id)
        assert document is not None
        assert document.title_text == "A complete searchable projection"
        assert "Question to answer:" in document.searchable_text
        assert "Handling instructions:" in document.searchable_text
        assert document.embedding_state is EmbeddingState.PENDING

    vector = [0.25] * EMBEDDING_DIMENSIONS
    provider = StubProvider([vector])
    indexer = RequestSearchIndexer(api_harness.sessions, provider, batch_size=8)
    assert await indexer.reconcile_once() is True
    assert provider.calls[0][0].startswith("Title: A complete searchable projection")
    assert await indexer.reconcile_once() is False
    async with api_harness.sessions() as session:
        document = await session.get(RequestSearchDocument, request_id)
        assert document is not None
        assert document.embedding == vector
        assert document.embedding_model == provider.model_name
        assert document.embedding_state is EmbeddingState.READY
        assert document.indexed_at is not None


async def test_indexer_rejects_misaligned_results_and_ignores_stale_rows(
    api_harness: ApiHarness,
) -> None:
    await submit(api_harness, "Pending projection")
    indexer = RequestSearchIndexer(api_harness.sessions, StubProvider([]), batch_size=1)
    with pytest.raises(ValueError, match="wrong number"):
        await indexer.reconcile_once()
    await indexer._store_vectors(
        [PendingSearchDocument(uuid4(), 1, "stale")],
        [[0.0] * EMBEDDING_DIMENSIONS],
    )


class FakeVector:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def astype(self, _type: type[float]) -> FakeVector:
        return self

    def tolist(self) -> list[float]:
        return self.values


class FakeTextEmbedding:
    created: ClassVar[list[dict[str, Any]]] = []
    values: ClassVar[list[list[float]]] = [[0.1] * EMBEDDING_DIMENSIONS]

    def __init__(self, **kwargs: Any) -> None:
        self.created.append(kwargs)

    def embed(self, _texts: object) -> list[FakeVector]:
        return [FakeVector(value) for value in self.values]


async def test_fastembed_boundary_is_lazy_offline_and_validates_vectors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    import mist_service.request_embeddings as embedding_module

    FakeTextEmbedding.created.clear()
    FakeTextEmbedding.values = [[0.1] * EMBEDDING_DIMENSIONS]
    monkeypatch.setattr(embedding_module, "TextEmbedding", FakeTextEmbedding)
    provider = FastEmbedRequestEmbeddingProvider(
        model_name="synthetic/model", cache_path=tmp_path, threads=1
    )
    assert await provider.embed([]) == []
    assert FakeTextEmbedding.created == []
    assert len((await provider.embed(["first request"]))[0]) == EMBEDDING_DIMENSIONS
    assert FakeTextEmbedding.created[0]["local_files_only"] is True
    await provider.embed(["second request"])
    assert len(FakeTextEmbedding.created) == 1

    FakeTextEmbedding.values = [[float("nan")] * EMBEDDING_DIMENSIONS]
    with pytest.raises(ValueError, match="invalid vector"):
        await provider.embed(["invalid"])
    FakeTextEmbedding.values = [[0.1]]
    with pytest.raises(ValueError, match="invalid vector"):
        await provider.embed(["wrong dimension"])


async def test_hybrid_scoring_is_explainable_and_remains_human_support(
    api_harness: ApiHarness,
) -> None:
    candidate_json = await submit(api_harness, "Northern readiness baseline")
    source_json = await submit(api_harness, "Northern readiness update")
    async with api_harness.sessions() as session:
        rows = (
            await session.execute(
                select(ServiceRequest, RequestSearchDocument).join(
                    RequestSearchDocument,
                    RequestSearchDocument.request_id == ServiceRequest.id,
                )
            )
        ).all()
        by_id = {str(request.id): (request, document) for request, document in rows}
        source, source_document = by_id[source_json["id"]]
        candidate, candidate_document = by_id[candidate_json["id"]]

    vector = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
    source_document.embedding = vector
    source_document.embedding_state = EmbeddingState.READY
    candidate_document.embedding = vector
    candidate_document.embedding_state = EmbeddingState.READY
    matches = score_candidates(
        source,
        source_document,
        [SearchCandidate(candidate, candidate_document, True)],
        query=None,
        limit=10,
    )
    assert matches[0].match_band is RelatedRecordMatchBand.STRONG
    assert "SEMANTIC" in matches[0].methods
    assert matches[0].evidence
    assert matches[0].product_available is True

    source_document.embedding = [0.0] * EMBEDDING_DIMENSIONS
    assert score_candidates(
        source,
        source_document,
        [SearchCandidate(candidate, candidate_document, False)],
        query=None,
        limit=10,
    )
    candidate_document.embedding_state = EmbeddingState.PENDING
    assert (
        "SEMANTIC"
        not in score_candidates(
            source,
            source_document,
            [SearchCandidate(candidate, candidate_document, False)],
            query=candidate.reference,
            limit=10,
        )[0].methods
    )

    for attribute in FIELD_WEIGHTS:
        setattr(candidate, attribute, "zyxw9876")
    candidate.customer_urgency = "IMMEDIATE"
    candidate.coverage_start = date(2031, 1, 1)
    candidate.coverage_end = date(2031, 1, 2)
    candidate.required_by = date(2031, 1, 3)
    candidate.sensitivity = "RESTRICTED"
    assert (
        score_candidates(
            source,
            source_document,
            [SearchCandidate(candidate, candidate_document, False)],
            query=None,
            limit=10,
        )
        == []
    )


@pytest.mark.parametrize(
    ("strength", "band"),
    [
        (70, RelatedRecordMatchBand.STRONG),
        (35, RelatedRecordMatchBand.POSSIBLE),
        (34, RelatedRecordMatchBand.LIMITED),
    ],
)
def test_match_bands_and_significant_terms(
    strength: int, band: RelatedRecordMatchBand
) -> None:
    assert _match_band(strength) is band
    assert significant_terms("The north NORTH readiness", limit=2) == [
        "north",
        "readiness",
    ]


class ScalarSession:
    def __init__(self, results: list[list[Any]]) -> None:
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        self.results = results
        self.statements: list[object] = []

    async def scalars(self, statement: object) -> list[Any]:
        self.statements.append(statement)
        return self.results.pop(0)


async def test_postgres_candidate_queries_cover_text_reference_trigram_and_vector() -> (
    None
):
    first, second = uuid4(), uuid4()
    session = ScalarSession([[first], [second]])
    search = RelatedRecordSearch(cast(AsyncSession, session))
    membership = ServiceRequest.id.is_not(None)
    assert (
        await search._postgres_text_ids(uuid4(), membership, " ", query=None) == set()
    )
    assert await search._postgres_text_ids(
        uuid4(), membership, "readiness", query="SR-2026"
    ) == {first, second}
    assert len(session.statements) == 2

    vector_session = ScalarSession([[first]])
    vector_search = RelatedRecordSearch(cast(AsyncSession, vector_session))
    assert await vector_search._postgres_vector_ids(
        uuid4(), membership, [0.0] * EMBEDDING_DIMENSIONS
    ) == {first}


async def test_postgres_candidate_pool_combines_modes_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_id, semantic_id = uuid4(), uuid4()
    session = ScalarSession([])
    search = RelatedRecordSearch(cast(AsyncSession, session))
    text_search = AsyncMock(return_value=set())
    vector_search = AsyncMock(return_value={semantic_id})
    monkeypatch.setattr(search, "_postgres_text_ids", text_search)
    monkeypatch.setattr(search, "_postgres_vector_ids", vector_search)
    source = ServiceRequest(
        id=uuid4(),
        title="Synthetic title",
        question_to_answer="What is required?",
        desired_outcome="A useful result",
        subject_area_or_location="North",
    )
    document = RequestSearchDocument(
        request_id=source.id,
        document_version=1,
        title_text="Synthetic title",
        question_text="What is required?",
        outcome_text="A useful result",
        context_text="North",
        searchable_text="Synthetic title",
        embedding=[0.0] * EMBEDDING_DIMENSIONS,
    )
    membership = ServiceRequest.id.is_not(None)
    assert await search._candidate_ids(source, document, membership, query=None) == {
        semantic_id
    }
    vector_search.assert_awaited_once()

    fallback_search = RelatedRecordSearch(
        cast(AsyncSession, ScalarSession([[fallback_id]]))
    )
    monkeypatch.setattr(
        fallback_search, "_postgres_text_ids", AsyncMock(return_value=set())
    )
    monkeypatch.setattr(
        fallback_search, "_postgres_vector_ids", AsyncMock(return_value=set())
    )
    assert await fallback_search._candidate_ids(
        source, document, membership, query=None
    ) == {fallback_id}

    manual_search = RelatedRecordSearch(
        cast(AsyncSession, ScalarSession([[fallback_id]]))
    )
    monkeypatch.setattr(
        manual_search, "_postgres_text_ids", AsyncMock(return_value=set())
    )
    assert await manual_search._candidate_ids(
        source, document, membership, query="manual"
    ) == {fallback_id}


async def test_requester_has_no_related_record_search_scope() -> None:
    session = cast(AsyncSession, SimpleNamespace())
    result = await RelatedRecordSearch(session).search(
        uuid4(),
        Actor(uuid4(), "customer", "Customer", UserRole.REQUESTER, "Area"),
        query=None,
        limit=10,
    )
    assert result.mode == "TEXT_ONLY"
    assert result.items == []
