# ADR 0006: Explicit Management Grants

## Status

Accepted for implementation.

## Context

Managers need statistics and selected workspace actions at JIOC, command, Ops and
team levels. Product roles describe workflow duties, but do not safely express
which organisational branch a person manages. Inferring authority from a role or
from a current membership would overexpose siblings and make temporary or
delegated authority difficult to audit.

## Decision

- Store versioned management grants in PostgreSQL independently from product
  roles and team memberships.
- A grant names one subject, one organisation root, exact-only or descendant
  scope, effective dates and independent actions for statistics, roster,
  calendar, board and capacity.
- Store a cycle-safe organisation closure table for bounded ancestor and
  descendant checks. Organisational mutations update the closure transactionally
  and reject cycles.
- Authorise each request by loading the active account, grant and target unit in
  the final application-service transaction. Never trust a client-provided role,
  path or descendant list.
- Require an expected version and mandatory reason to add, alter, revoke or
  expire a grant. Keep historical grants.
- Seed explicit local grants for the named JIOC, command, Ops and Team Manager
  fixtures. Multiple explicit grants are permitted.
- Keep Platform Administrator identity governance separate. Administration does
  not imply service-request content access.

## Consequences

The same user can hold narrowly different authorities without new application
roles. Revocation and expiry are immediate and attributable. Every workspace can
reuse one policy boundary. The extra closure and grant data requires migration,
concurrency controls and comprehensive ancestor, descendant and sibling tests.

## Rejected alternatives

- Add a role for every management level: role count grows with the hierarchy and
  still fails to identify an exact branch.
- Infer scope from current team membership: unsuitable for command and Ops
  managers and unsafe for delegation.
- Trust the frontend navigation tree: it is not an authorisation boundary.
