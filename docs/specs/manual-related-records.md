# Manual Related-Record Checks

## Outcome

During an actively claimed JIOC intake task, the routing user can search the
requests they are authorised to handle and record a possible duplicate, related
request or existing released product. The feature records human judgement. It
does not rank, recommend, infer or automatically change workflow state.

## Users and permissions

- Only an active JIOC Routing User who owns the current `TRIAGE_REVIEW` task may
  search or add links for that request.
- Search candidates must share an organisation route that the actor currently
  belongs to. The current request is excluded.
- Customers, command users, Ops users, team users, QC users and Platform
  Administrators cannot access the endpoints.
- Links remain visible to the owning JIOC user while the intake task is active
  and become an attributable request-history event for later audit.

## Data and behaviour

- Search is bounded to 20 results and matches a normalised reference or title.
- Candidate results contain only request ID, reference, title, status,
  required-by date and whether a released product exists.
- A link has one of `POSSIBLE_DUPLICATE`, `RELATED_REQUEST` or
  `EXISTING_OUTPUT`, a mandatory reason, actor, source, target and timestamp.
- `EXISTING_OUTPUT` is valid only when the target has a released product.
- Source and target cannot be the same. The same typed link cannot be added
  twice. Links are append-only.
- Link creation locks and version-checks the source request, rechecks the active
  actor, task ownership, stage and route membership, increments the source
  version and appends a hash-linked request event in the same transaction.

## Error behaviour

- Out-of-scope source, target or actor returns not found without disclosing the
  object.
- Stale source versions return the standard conflict response.
- Invalid self-links, duplicate links and existing-output links without a
  released product return a safe conflict.
- Search terms shorter than two characters or above 120 characters are rejected
  by FastAPI before persistence is queried.

## Accessibility and interaction

The intake detail provides a labelled search field, an explicit Search button,
keyboard-operable results, visible result counts, required link type and reason,
and loading, empty, error, conflict and success states. It never links by drag
and drop.

## Acceptance criteria

1. An owning JIOC user can find an authorised candidate and store each link type.
2. Existing links persist across refresh and include actor and time.
3. Another JIOC user without ownership, every other role, a stale session and a
   user whose membership is removed receive no data and cannot mutate.
4. Self, duplicate, stale-version and unreleased-output attempts fail safely.
5. Candidate searches cannot return records outside the actor's route membership.
6. Concurrent identical submissions have exactly one winner.
7. API, React, migration, audit-integrity and accessibility tests pass without
   lowering coverage.

## Non-goals

- automated similarity, recommendations, ranking or routing;
- full-text indexing of request narrative or service-product content;
- opening an existing product from the intake result;
- deleting or silently editing a recorded judgement; and
- searching external systems.
