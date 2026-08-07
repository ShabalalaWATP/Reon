# ADR 0015: Action Projections and Notification Delivery

## Status

Accepted for implementation on 7 August 2026. Acceptance of this record does not
prove implementation or release readiness.

## Context

Users need one personal view of work drawn from Camunda human tasks and
application-owned duties. They also need durable notice when relevant state
changes. A convenient inbox must not become another workflow authority, grant
access, expose protected content or duplicate notifications during retry and
reconciliation.

## Decision

- Store action items as rebuildable PostgreSQL read projections. Every item
  identifies its authoritative source, source version, freshness and permitted
  deep link. Camunda remains authoritative for human-task lifecycle.
- Assemble `My work` through source-specific adapters and apply current role,
  assignment, object and organisation policy on every query. Projection presence
  is never proof of access.
- Permit action rows and notification links to invoke only named application use
  cases. They cannot directly change a route, priority, assignee, approval,
  dissemination recipient or Camunda state.
- Publish notification-worthy domain events transactionally through the existing
  outbox. Derive recipients with server-owned policy and use the source event plus
  recipient as the stable idempotency key.
- Store unread, read, archived and action-completed state separately from the
  authoritative action. Re-evaluate recipient access on every list, count and
  deep-link request.
- Keep notification subjects content-minimal. Request narrative, clarification
  text, product content, Customer identity and private calendar text are not
  notification data.
- Use live refresh only as a delivery optimisation. Bounded polling,
  reconciliation and visible freshness provide the recovery path.

## Consequences

- The personal workspace can be rebuilt without moving or inventing workflow
  state.
- Retry and replay can be proved idempotent per event and recipient.
- Ended memberships, revoked grants and disabled accounts remove live access even
  when an older notification remains in audit history.
- Recipient rules, lag thresholds, reminder windows and retention require owned,
  versioned configuration before release.

## Rejected alternatives

- Treat inbox rows as the task system: this would conflict with Camunda and
  application aggregates.
- Authorise from notification possession: a copied identifier would become an
  access token.
- Put narrative excerpts in notifications: this would enlarge the leakage and
  retention boundary without helping users identify the required action.
