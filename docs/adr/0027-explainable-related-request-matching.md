# ADR 0027: Explainable related-request matching

Status: accepted, 10 August 2026.

## Context

CRIOC reviewers need an authorised comparison across all Customer-submitted
request content, with a meaningful relevance order and understandable evidence.
The capability must remain useful when a semantic model is unavailable, preserve
the human-led workflow and organisation scope, and keep request content away from
external model providers.

## Decision

Create one PostgreSQL search projection for every submitted request. Use a
generated weighted `tsvector` with a GIN index for immediate text retrieval and
a 384-dimension pgvector column with an HNSW cosine index for semantic
retrieval. Form a bounded union of indexed text and vector candidates, then
apply one deterministic score across field overlap, semantic similarity and
small structured boosts.

Generate embeddings with FastEmbed and `BAAI/bge-small-en-v1.5`. Bake the model
into the backend image and require offline-only runtime loading. A named,
lease-fenced worker indexes pending projections. Submission creates the text
projection transactionally but never waits for model work.

Authorise the source task before search and apply the same route-membership
predicate independently to lexical and vector candidate queries. Return
deterministic field-level explanations and bounded excerpts. Retain append-only
human decisions, including a new not-relevant outcome, without changing
Camunda state.

## Consequences

- CRIOC receives automatic, explainable candidates without guessing a title.
- Every submitted request is searchable immediately through text ranking and
  gains semantic ranking asynchronously.
- PostgreSQL remains the only request and search datastore.
- The backend image is larger because it contains the embedding runtime and
  revision and checksum-verified model cache. Image scanning, licences and
  model provenance become release evidence.
- Model upgrades require an explicit projection version and controlled re-index.
- Text-only fallback is honest and does not block the human workflow.

## Rejected alternatives

- Title/reference substring search, because it ignores the requirement and has
  no meaningful relevance ordering.
- An external hosted embedding API, because submitted request content would
  cross a new boundary without an approved provider or handling agreement.
- Vector-only retrieval, because exact references and phrases remain important
  and model outages must not remove search.
- Automatically closing or routing likely duplicates, because the MVP routing
  decisions are explicitly human-led.
- A separate search datastore, because PostgreSQL full-text search and pgvector
  meet the MVP scale without a second backup, authorisation and recovery domain.
