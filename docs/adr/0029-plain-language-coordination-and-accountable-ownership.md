# ADR 0029: Plain-language coordination and accountable ownership

## Status

Accepted, 10 August 2026.

## Context

The former coordination label described an implementation stage rather than a
user's task. The personal action register also displayed the generic stage
owner before a person claimed the work, obscuring which configured unit was
responsible.

## Decision

Use `Incoming requests` for the queue and `Request coordination` for the role
and lifecycle stage. Preserve internal role, status, action and BPMN element
identifiers.

For a shared routed action, resolve its pinned organisation unit at read time
and present `<unit> · Awaiting owner`. For a personally assigned action, present
the claimant's display name. The stored projection remains an auditable source
snapshot, while the response reflects current authorised organisation naming.

## Consequences

- Staff see task-oriented language without a workflow-engine vocabulary.
- Existing actions and renamed units are corrected without a data migration.
- The distinction between unit responsibility and individual accountability is
  explicit.
- API consumers must treat `currentOwner` as presentation text, not as a stable
  identifier. Stable user and organisation identifiers remain separate fields.
