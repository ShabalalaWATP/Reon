# ADR 0002: Secure Modular Foundations

## Status

Accepted, 6 August 2026.

## Context

The MVP is small, but it handles scoped requests, human assignments, approvals
and disseminated products. Fast delivery must not create route-level business logic,
UI-only access control, an engine-shaped domain model or infrastructure coupling
that makes later draft, note, workload and administration capabilities unsafe to
add.

## Decision

Use four explicit dependency directions:

1. Domain entities, value objects and transition policy contain framework-free
   business rules.
2. Application use cases coordinate policy and transactions through small ports.
3. HTTP routes, schemas and React features translate delivery concerns only.
4. SQLAlchemy, Camunda, password, session and observability adapters implement
   ports and depend inwards.

Apply SOLID pragmatically:

- Single responsibility: separate authentication, authorisation, request
  lifecycle, workflow synchronisation, audit and presentation concerns.
- Open/closed: add a use case or adapter behind an existing boundary when the
  behaviour is genuinely new; do not build speculative plug-in registries.
- Liskov substitution: test real and in-memory repository and workflow adapters
  against the same behavioural contracts.
- Interface segregation: expose narrow ports for the operations each use case
  needs instead of a universal service or repository.
- Dependency inversion: application policy depends on protocols for persistence,
  workflow, identity, time and audit, never directly on external clients.

Security is a design input:

- Deny access unless role, operational scope, object ownership, assignment and
  expected state all permit the action.
- Enforce policy in backend query and mutation paths. UI route policy is only a
  usability layer.
- Give the Platform Administrator no implicit request-content access.
- Use opaque server-side sessions, Argon2id, CSRF protection, trusted origins,
  bounded login failures and secure production cookies.
- Make submitted revisions append-only and workflow events tamper-evident with a
  hash chain. Never treat application logs as the audit record.
- Use a transactional outbox and idempotency keys for every cross-system workflow
  command.
- Validate untrusted input at API and persistence boundaries, constrain queries,
  render user content as text and exclude binary files until separately secured.
- Emit structured operational metadata without bodies, credentials, tokens or
  sensitive content.
- Keep configuration typed, fail closed outside local mock-data mode and use separate
  least-privileged database identities.

## Verification

- Unit-test domain policy and use cases without starting HTTP or Camunda.
- Contract-test persistence and workflow adapters.
- Integration-test transactions, outbox recovery, migrations and PostgreSQL
  semantics that SQLite cannot represent.
- Exercise cross-role, cross-scope, direct-identifier and invalid-transition
  cases at the API boundary.
- Test keyboard operation, focus, accessible names, errors, contrast and reduced
  motion across representative UI journeys.
- Verify backup and restore, audit-chain integrity, health endpoints and failure
  recovery before pilot exit.

## Consequences

There are a few more small modules and explicit interfaces, but business rules
remain testable and replaceable. The design deliberately avoids a generic
dependency container, universal repository, global event bus and other
abstractions that do not yet protect a real boundary.
