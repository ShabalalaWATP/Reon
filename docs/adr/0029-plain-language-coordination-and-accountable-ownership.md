# ADR 0029: Plain-language coordination and accountable ownership

## Status

Accepted, 10 August 2026.

## Context

Coordination work belongs to the selected organisation unit until a named person
claims it. The interface must describe the required human task and distinguish
unit responsibility from personal accountability.

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
- Current actions resolve the authorised unit name at read time.
- The distinction between unit responsibility and individual accountability is
  explicit.
- API consumers must treat `currentOwner` as presentation text, not as a stable
  identifier. Stable user and organisation identifiers remain separate fields.
