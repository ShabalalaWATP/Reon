# ADR 0009: Workflow-Derived Boards and Separate Work Packages

## Status

Accepted for implementation.

## Context

Teams need Kanban, backlog and capacity features, but service requests already
have an authoritative Camunda process. Treating a draggable board column as an
independent state would permit workflow steps, permissions and audit evidence to
be bypassed.

## Decision

- Project service-request cards from authoritative request and Camunda task state
  into stable board columns.
- A board move is a presentation of a named, authorised application command. If
  there is no valid workflow command for the source and target, the move is not
  offered and is rejected by the server.
- Use the existing transactional outbox for workflow actions and reconcile the
  board projection idempotently.
- Keep team-created work packages in PostgreSQL as a separate aggregate with
  optimistic versioning, immutable activity, dependencies and reservations.
- A package may link to a request for planning context but cannot mutate request
  route, status, assignment or product.
- Package-list reads are explicitly bounded and assemble related contributors,
  dependencies, activity and reservations in bulk. A list must not issue a set
  of related-record queries for every package row.
- Calculate WIP limits and capacity warnings at the application-service boundary.
  They guide authorised human choices and do not auto-route work.
- Support a non-drag command menu and table view for keyboard and narrow-screen
  use.

## Consequences

The board stays consistent with the executable process and retains human-led
decisions. Team planning can evolve without destabilising request state. The UI
must handle pending workflow commands and projection freshness explicitly.

## Rejected alternatives

- Let drag-and-drop write request status directly: creates a second workflow
  engine and breaks authorisation.
- Model all planning packages as Camunda processes: unnecessary engine load and
  poor fit for ordinary team backlog work.
- Add a general project-management platform: exceeds the bounded MVP and divides
  the source of truth.
