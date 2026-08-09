# Runtime scaling and worker hardening specification

Status: implemented and target-scale evidenced
Last reviewed: 8 August 2026

## Objective

Remove avoidable database and API-replica coupling from the ISTARI pilot while
preserving human-led routing, object-level authorisation, durable recovery and
the existing user journeys. This milestone implements the accepted
simplification findings except atomic concurrent Board WIP enforcement, which
is explicitly outside scope.

## Scope

| ID | Requirement | Acceptance evidence |
|---|---|---|
| RSW-01 | HTTP requests never run organisation-membership timeline reconciliation | Dependency and request query-count tests |
| RSW-02 | A separately executable worker applies only due membership transitions under an expiring database lease | Lease takeover, due-transition and fail-closed tests |
| RSW-03 | API readiness derives worker health from a durable heartbeat rather than an in-process task | API/worker lifecycle and stale-heartbeat tests |
| RSW-04 | Human workflow commands commit a fenced lease before Camunda I/O and revalidate the exact command under a new transaction before projection | transaction-boundary, stale-lease, retry and recovery tests |
| RSW-05 | Managed upload, scan and promotion I/O occurs outside metadata lock transactions and uses a fenced upload-intent lease where duplicate work is unsafe | storage/scanner transaction-probe and lease tests |
| RSW-06 | Managed product downloads authorise and audit before returning a stream, and no request-scoped database session remains open while bytes are yielded | slow-stream and cancellation tests |
| RSW-07 | Work, request, draft, tracking, administrator, request-history and Board feeds use opaque keyset cursors with bounded database reads | page-boundary, invalid-cursor and statement-count tests |
| RSW-08 | PostgreSQL indexes match the leading scope, filter and ordering columns of the bounded feeds and maintenance queues | migration inspection and `EXPLAIN (ANALYSE, BUFFERS)` evidence |
| RSW-09 | Board filters execute in PostgreSQL and each source contributes at most `limit + 1` candidates before a bounded merge | SQL shape, query-count and functional parity tests |
| RSW-10 | Worker jobs are independently leased and safe when multiple worker replicas overlap or one lease expires | multi-worker contention tests |
| RSW-11 | Dense React orchestration, repeated work-package form fields and broad API contracts are split by domain without changing visible behaviour | frontend tests, Knip, TypeScript and bundle budget |
| RSW-12 | The agreed synthetic target scale has repeatable statement counts, query plans, contention results, HTTP load and browser navigation measurements | generated performance evidence with commands and hashes |

## Security and correctness invariants

- Membership compatibility rows are an authorisation input. When a due
  transition cannot be proved applied, affected future membership must not be
  granted early. The durable timeline remains authoritative.
- A lease is a fencing token, not an authorisation token. Finalisation must
  compare job name, owner and generation and must re-run object and actor policy.
- No database transaction may remain open during Camunda, object-storage,
  malware-scanner or response-stream I/O.
- A timed-out worker may finish its external call, but it may not project a
  result after another worker acquires a later lease generation.
- Keyset cursors contain ordering keys only. They carry no content or authority,
  are bounded at the HTTP boundary and fail closed when malformed.
- Pagination must never widen role, route, team or requester scope.
- Product access audits are committed independently of the download stream and
  contain metadata only.

## Pagination contract

- Default page size is 50 and maximum page size is 100.
- Mutable operational feeds use descending `(updated_at, id)` ordering.
- Append-only request history uses descending `(created_at, id)` ordering.
- Administrator users use descending `(updated_at, id)` ordering.
- Board ordering remains descending `(updated_at, item_type, id)` so existing
  cursors and visual order remain stable.
- Responses expose `nextCursor`; clients append pages and reset pagination when
  a filter changes.

## Worker contract

The `istari-worker` process owns workflow-start dispatch, workflow-command
dispatch, task reconciliation, notification projection and scheduled membership
projection. Each loop:

1. records a durable heartbeat;
2. executes bounded work, with outbox rows retaining their existing per-item
   leases;
3. acquires named expiring leases for singleton reconciliation jobs;
4. records success or a content-free failure code;
5. uses bounded idle backoff when no work is available.

The API performs no maintenance work. Local Docker runs one worker service;
production may run multiple replicas because work and singleton jobs are
fenced.

## Performance target

The synthetic evidence target is at least:

- 250 active users;
- 2,500 Board packages;
- 5,000 calendar occurrences;
- 2,500 requester, work, tracking and history rows where the fixture supports
  the scope;
- two overlapping worker replicas in the contention rehearsal;
- ordinary page/API p95 below two seconds at the documented pilot concurrency;
- bounded statement counts that do not increase with page depth.

Measurements are environment-specific evidence, not a universal capacity
claim. Connected production remains subject to the production gates.

## Acceptance result

The current source passed the full requirement set on 8 August 2026, except the
explicit WIP exclusion below. A clean PostgreSQL 17.9 database migrated to
`0019_runtime_scaling` and held 2,500 request, draft, work and history rows,
2,500 Board packages, 5,000 calendar events and 250 active users.

First-page and depth-2,400 statement counts were identical: one statement for
request, draft, work, administrator and Board reads, four for tracking and seven
for the complete request-detail/history projection. Every required index was
present and compatible with `EXPLAIN (ANALYSE, BUFFERS)`. Two overlapping
workers executed one named callback exactly once. A 2,500-request, 25-user HTTP
run returned 2,500 HTTP 200 responses, with 473.19 ms p95 and 576.60 ms p99.
Production-built browser journeys loaded a second Customer, routing, Board and
administrator page in 31.6 to 51.7 ms locally.

The final clean regression run passed 858 backend tests at 98.83 per cent line
and 95.18 per cent branch coverage. The frontend passed 284 tests at 99.49 per
cent statements and 95.06 per cent branches. Both dimensions are enforced
independently at a 95 per cent floor.

The content-free raw results and Playwright trace hashes are indexed by
`output/load/runtime-scale-manifest.json`. These generated local artefacts are
not source-controlled release evidence. A release candidate must rerun and
retain them in its approved evidence store.

## Explicit exclusion

Atomic concurrent Board WIP-limit enforcement is not part of this milestone at
the user's direction. Existing advisory enforcement remains, and the residual
race stays recorded as an accepted MVP limitation until separately authorised.
