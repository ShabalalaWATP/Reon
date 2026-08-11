"""Deterministic and explainable ranking for related service requests."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Final

from istari_service.models import ServiceRequest
from istari_service.request_search_models import (
    EmbeddingState,
    RequestSearchDocument,
)
from istari_service.request_search_text import SEARCH_FIELDS, request_field_values
from istari_service.schemas.related_records import (
    RelatedRecordEvidence,
    RelatedRecordMatch,
    RelatedRecordMatchBand,
    RelatedRecordMatchMethod,
)

TOKEN_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9'-]{1,}")
STOP_WORDS: Final = frozenset(
    {
        "about",
        "after",
        "also",
        "and",
        "are",
        "for",
        "from",
        "have",
        "into",
        "not",
        "only",
        "that",
        "the",
        "their",
        "this",
        "through",
        "use",
        "what",
        "when",
        "where",
        "which",
        "with",
    }
)
FIELD_WEIGHTS: Final = {
    "title": 2.2,
    "description": 1.2,
    "question_to_answer": 2.2,
    "desired_outcome": 1.7,
    "background_context": 1.0,
    "subject_area_or_location": 1.5,
    "supported_activity_or_decision": 1.2,
    "required_by_reason": 0.8,
    "preferred_deliverable_type": 1.0,
    "success_criteria": 1.0,
    "constraints_or_caveats": 0.5,
    "supporting_information": 0.6,
    "handling_instructions": 0.3,
}
LABELS: Final = {attribute: label for label, attribute in SEARCH_FIELDS}


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    request: ServiceRequest
    document: RequestSearchDocument
    product_available: bool


def significant_terms(value: str, *, limit: int = 16) -> list[str]:
    tokens = TOKEN_PATTERN.findall(unicodedata.normalize("NFKC", value).casefold())
    return list(dict.fromkeys(token for token in tokens if token not in STOP_WORDS))[
        :limit
    ]


def score_candidates(
    source: ServiceRequest,
    source_document: RequestSearchDocument,
    candidates: list[SearchCandidate],
    *,
    query: str | None,
    limit: int,
) -> list[RelatedRecordMatch]:
    matches = [
        _score_candidate(source, source_document, candidate, query=query)
        for candidate in candidates
    ]
    threshold = 5 if query else 12
    return sorted(
        (match for match in matches if match.match_strength >= threshold),
        key=lambda item: (-item.match_strength, item.required_by, item.reference),
    )[:limit]


def _score_candidate(
    source: ServiceRequest,
    source_document: RequestSearchDocument,
    candidate: SearchCandidate,
    *,
    query: str | None,
) -> RelatedRecordMatch:
    source_values = request_field_values(source)
    target_values = request_field_values(candidate.request)
    field_scores = _field_scores(source_values, target_values)
    lexical = _lexical_score(source_values, target_values, field_scores)
    structured, structured_reasons = _structured_score(source, candidate.request)
    semantic = _semantic_score(source_document, candidate.document)
    query_score = (
        _query_score(query, target_values, candidate.request.reference)
        if query
        else None
    )
    if query_score is not None:
        combined = (
            0.85 * query_score + 0.10 * lexical + 0.05 * structured
            if query_score > 0
            else 0.0
        )
    elif semantic is not None:
        combined = 0.50 * semantic + 0.40 * lexical + 0.10 * structured
    else:
        combined = 0.85 * lexical + 0.15 * structured

    evidence = _evidence(
        target_values,
        field_scores,
        query=query,
        structured_reasons=structured_reasons,
    )
    strength = min(100, max(0, round(combined * 100)))
    methods: list[RelatedRecordMatchMethod] = []
    if query_score or lexical:
        methods.append(RelatedRecordMatchMethod.FULL_TEXT)
    if semantic is not None:
        methods.append(RelatedRecordMatchMethod.SEMANTIC)
    if structured:
        methods.append(RelatedRecordMatchMethod.STRUCTURED)
    return RelatedRecordMatch(
        id=candidate.request.id,
        reference=candidate.request.reference,
        title=candidate.request.title,
        status=candidate.request.status,
        required_by=candidate.request.required_by,
        product_available=candidate.product_available,
        match_strength=strength,
        match_band=_match_band(strength),
        methods=methods,
        reasons=[item.reason for item in evidence],
        evidence=evidence,
    )


def _field_scores(
    source: dict[str, str], target: dict[str, str]
) -> dict[str, tuple[float, set[str]]]:
    result: dict[str, tuple[float, set[str]]] = {}
    for attribute in FIELD_WEIGHTS:
        left, right = (
            set(significant_terms(source[attribute], limit=80)),
            set(significant_terms(target[attribute], limit=80)),
        )
        shared = left & right
        denominator = len(left) + len(right)
        result[attribute] = (
            (2 * len(shared) / denominator) if denominator else 0.0,
            shared,
        )
    return result


def _lexical_score(
    source: dict[str, str],
    target: dict[str, str],
    field_scores: dict[str, tuple[float, set[str]]],
) -> float:
    weighted = sum(
        field_scores[field][0] * weight for field, weight in FIELD_WEIGHTS.items()
    ) / sum(FIELD_WEIGHTS.values())
    source_all = set(significant_terms(" ".join(source.values()), limit=300))
    target_all = set(significant_terms(" ".join(target.values()), limit=300))
    denominator = len(source_all) + len(target_all)
    global_score = (
        2 * len(source_all & target_all) / denominator if denominator else 0.0
    )
    return 0.65 * weighted + 0.35 * global_score


def _query_score(query: str, target: dict[str, str], reference: str) -> float:
    query_terms = set(significant_terms(query, limit=40))
    if not query_terms:
        return 0.0
    target_terms = set(
        significant_terms(f"{reference} {' '.join(target.values())}", limit=400)
    )
    return len(query_terms & target_terms) / len(query_terms)


def _semantic_score(
    source: RequestSearchDocument,
    target: RequestSearchDocument,
) -> float | None:
    if (
        source.embedding_state is not EmbeddingState.READY
        or target.embedding_state is not EmbeddingState.READY
        or source.embedding is None
        or target.embedding is None
    ):
        return None
    denominator = math.sqrt(sum(x * x for x in source.embedding)) * math.sqrt(
        sum(x * x for x in target.embedding)
    )
    cosine = (
        sum(x * y for x, y in zip(source.embedding, target.embedding, strict=True))
        / denominator
        if denominator
        else 0.0
    )
    return min(1.0, max(0.0, (cosine - 0.30) / 0.70))


def _structured_score(
    source: ServiceRequest, target: ServiceRequest
) -> tuple[float, list[str]]:
    checks = (
        (
            source.preferred_deliverable_type.casefold()
            == target.preferred_deliverable_type.casefold(),
            0.35,
            "Same preferred deliverable type.",
        ),
        (
            source.customer_urgency == target.customer_urgency,
            0.20,
            "Same customer urgency.",
        ),
        (
            source.coverage_start <= target.coverage_end
            and target.coverage_start <= source.coverage_end,
            0.45,
            "Coverage periods overlap.",
        ),
    )
    reasons = [reason for matched, _, reason in checks if matched]
    return sum(weight for matched, weight, _ in checks if matched), reasons


def _evidence(
    target: dict[str, str],
    scores: dict[str, tuple[float, set[str]]],
    *,
    query: str | None,
    structured_reasons: list[str],
) -> list[RelatedRecordEvidence]:
    query_terms = set(significant_terms(query or "", limit=40))
    ranked: list[tuple[float, str, set[str]]] = []
    for field, weight in FIELD_WEIGHTS.items():
        score, shared = scores[field]
        if query:
            shared = query_terms & set(significant_terms(target[field], limit=100))
            score = len(shared) / len(query_terms) if query_terms else 0.0
        if shared:
            ranked.append((score * weight, field, shared))
    ranked.sort(reverse=True)
    evidence = [
        RelatedRecordEvidence(
            field=LABELS[field],
            reason=(
                f"Matches {len(shared)} search term"
                f"{'s' if len(shared) != 1 else ''} in {LABELS[field].lower()}."
                if query
                else f"{LABELS[field]} shares {len(shared)} significant term"
                f"{'s' if len(shared) != 1 else ''}."
            ),
            excerpt=_excerpt(target[field]),
        )
        for _, field, shared in ranked[:3]
    ]
    remaining = 3 - len(evidence)
    evidence.extend(
        RelatedRecordEvidence(field="Request details", reason=reason, excerpt="")
        for reason in structured_reasons[:remaining]
    )
    return evidence


def _excerpt(value: str) -> str:
    return value if len(value) <= 220 else f"{value[:217].rstrip()}..."


def _match_band(strength: int) -> RelatedRecordMatchBand:
    if strength >= 70:
        return RelatedRecordMatchBand.STRONG
    if strength >= 35:
        return RelatedRecordMatchBand.POSSIBLE
    return RelatedRecordMatchBand.LIMITED
