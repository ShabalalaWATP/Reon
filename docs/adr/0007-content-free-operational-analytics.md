# ADR 0007: Content-Free Operational Analytics

## Status

Accepted for implementation. Analytical presentation amended on 10 August 2026.

## Context

Operational managers need traffic, delay, workload and service-quality measures
for only the units they manage. Calculating every view from request content is
slow, creates accidental disclosure risk and makes measure definitions difficult
to reproduce.

## Decision

- Keep PostgreSQL as the analytics store for the MVP. Do not add a warehouse or a
  second database technology.
- Project idempotent request facts and stage intervals from authoritative product
  and audit events through the existing outbox and reconciliation boundary.
- Facts contain stable request and organisation identifiers, dates, status,
  durations and categorical measure keys. They exclude request narrative,
  product content, Customer identity and feedback comments.
- Record metric definitions and projection version. Rebuild projections from
  authoritative history when the version changes.
- Query through the active management grant and organisation closure in the same
  repository query. Apply a bounded date range, pagination and statement timeout.
- Use a minimum cohort of five for rating aggregates and child-unit comparisons
  derived from feedback. Return `suppressed`, not zero, below the threshold.
- Return measure definitions, time zone, filter range, freshness and suppression
  metadata with every response.
- Provide tabular values as the API contract. Charts are accessible renderings of
  the same rows, not separate calculations.
- Use distribution and percentile-range graphics only for measures already in
  the authorised response, and retain labelled legends, textual summaries and
  table parity for interpretation without colour or motion.

## Consequences

Operational reporting stays local-first, reproducible and content-minimised.
Projection lag and rebuild state must be visible. Some real-time counts may be a
few seconds behind request detail, which is preferable to broad content reads.

## Rejected alternatives

- Query request bodies for every chart: unnecessary exposure and poor scaling.
- Use Camunda Optimize as the product reporting authority: it lacks product-level
  scope and would couple access policy to engine internals.
- Add a cloud analytics service: outside the local MVP and unnecessary at pilot
  scale.
