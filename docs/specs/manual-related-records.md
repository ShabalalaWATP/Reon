# Explainable Related-Request Matching

## Outcome

During an actively claimed JIOC intake task, ISTARI automatically compares the
new request with every previous submitted request the actor is authorised to
see. It ranks strong candidates using the complete Customer-submitted
requirement, explains the fields that contributed to each match and lets the
named JIOC user record a possible duplicate, related request, existing released
product or not-relevant decision.

Matching remains advisory. It never closes, merges, prioritises or routes a
request, and it never changes a Camunda variable.

## Search corpus

Every submitted `ServiceRequest` receives a search projection in the same
PostgreSQL transaction as submission. Drafts and account requests are excluded.
The projection combines:

- title, description and question to answer;
- desired outcome and background context;
- subject area or location and coverage period;
- Customer urgency and supported activity or decision;
- required-by reason and preferred deliverable type;
- success criteria, constraints and caveats;
- supporting information, sensitivity and handling instructions.

Existing requests are backfilled during migration. Active, completed,
cancelled and closed requests remain candidates. The current request is always
excluded.

## Retrieval and ranking

PostgreSQL remains authoritative. The ranked candidate set combines:

1. weighted PostgreSQL full-text ranking over the complete projection;
2. pgvector cosine similarity from the bundled local embedding model when its
   index is ready; and
3. deterministic structured boosts for deliverable type, urgency and
   overlapping coverage periods.

The database forms a bounded union of indexed lexical and semantic candidates,
then one deterministic weighted score orders them. A bounded match-strength
value helps order results but is not described as a probability. The text and
structured path remains available if semantic indexing is pending or
unavailable.

The automatic view returns at most ten candidates. Advanced search accepts a
two-to-240-character query and returns at most twenty candidates across the
same complete corpus. Results use required date and then reference as stable
tie-breakers.

## Explainability

Each result contains:

- match strength and `STRONG`, `POSSIBLE` or `LIMITED` band;
- whether lexical, semantic and structured evidence contributed;
- up to three field-level reasons;
- short, escaped excerpts from authorised fields;
- reference, title, status, required date and released-product availability;
- indexing mode so the interface can disclose a text-only fallback.

Explanations are deterministic. No generative model writes or summarises them.
The interface must not claim that a score proves a duplicate.

## Semantic indexing

The worker runs the English `BAAI/bge-small-en-v1.5` model through FastEmbed.
The model is downloaded into the backend image during build and is opened in
offline-only mode at runtime. Request content is never sent to an external
embedding provider. The model name, vector dimensions and projection version
are stored with each vector so upgrades can be re-indexed safely.

The existing named worker lease fences the indexer. A projection is created
immediately and semantic indexing is asynchronous, bounded and retryable. A
worker or model outage cannot block submission, routing or text search.

## Users and permissions

- Only an active JIOC Routing User who owns the current `TRIAGE_REVIEW` task may
  retrieve suggestions, search or add decisions for that request.
- Every lexical query, vector query, comparison and save re-applies the actor's
  route-membership condition before content or scores leave persistence.
- The source request, candidate request and released-product state are
  reauthorised when a decision is saved.
- Customers, command users, Ops users, delivery teams, QC users and Platform
  Administrators cannot access these endpoints.
- Search terms, source text, vectors, excerpts and scores are never written to
  application logs, audit events, metrics or Camunda variables.

## Human decisions

The append-only decisions are:

- `POSSIBLE_DUPLICATE`;
- `RELATED_REQUEST`;
- `EXISTING_OUTPUT`; and
- `NOT_RELEVANT`.

Each decision requires a reason of at least ten characters, actor, source,
target and timestamp. `EXISTING_OUTPUT` is valid only when the target still has
a released product. A later positive decision can coexist with an earlier
not-relevant decision only when each decision type is unique and attributable.

## Error and fallback behaviour

- Out-of-scope source, target or actor returns not found without disclosure.
- Stale source versions return the standard conflict response.
- Self-links, duplicate typed decisions and unavailable-product decisions fail
  safely.
- Embedding failure leaves the projection text-searchable and reports the
  fallback mode without exposing an internal error.
- Search terms are bounded before persistence is queried.
- The API returns no unbounded narrative, vector or internal rank components.

## Accessibility and interaction

The intake detail loads the automatic comparison but presents it as a compact,
collapsed summary so lower-confidence suggestions do not dominate the routing
decision. The summary distinguishes strong matches from optional suggestions.
Expanding it reveals manual search and a keyboard-focusable, fixed-height result
region with its own vertical scroll. Each result retains a labelled match band,
visible score, matched-field reasons and an expandable comparison without
relying on colour. Search, disclosure, scrolling, comparison and decision
controls are keyboard-operable and include loading, empty, partial-index, error,
conflict and success states.

## Acceptance criteria

1. Every submitted request creates one search projection atomically; drafts do
   not, and migration backfills all existing submitted requests.
2. Automatic suggestions search all Customer-submitted fields and exclude the
   source request.
3. Lexical, semantic and structured evidence produce deterministic ordering and
   field-level explanations on a fixed synthetic relevance corpus.
4. Text ranking remains usable when every embedding is absent or the indexer is
   unavailable.
5. Another JIOC user without ownership, every other role and users outside the
   route receive no candidate content or score.
6. Search and comparison cannot leak sibling or unrelated route content through
   results, timing-sensitive counts, excerpts or errors.
7. A named JIOC user can record each decision type; the action remains
   informational and cannot change workflow state.
8. PostgreSQL full-text and vector indexes, empty upgrade, downgrade, re-upgrade
   and drift checks pass.
9. Backend and frontend retain at least 95 per cent line and branch coverage.
10. Automatic results are collapsed by default, their summary does not describe
    lower-confidence suggestions as strong matches, and expansion cannot make
    the result list exceed its bounded scroll region.

## Non-goals

- automatic routing, closure, merging or prioritisation;
- searching private drafts, clarification messages or unreleased products;
- generative summaries or generated duplicate rationales;
- cross-organisation discovery outside the active actor's route; and
- treating match strength as certainty or an intelligence judgement.
