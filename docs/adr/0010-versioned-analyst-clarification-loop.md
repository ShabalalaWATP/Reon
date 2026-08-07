# ADR 0010: Versioned Analyst Clarification Loop

## Status

Accepted for implementation.

## Context

The current process supports intake clarification returning to JIOC. During
production an assigned Analyst may also need information from the Customer. That
conversation must pause work, retain the assignment, be visible in the Customer
dashboard and resume without travelling back through routing approvals.

## Decision

- Add a distinct Analyst clarification command and Customer-response user task to
  a new BPMN process version.
- Keep existing process instances pinned to their deployed definition version.
- Store the structured clarification thread in PostgreSQL before dispatching the
  idempotent workflow command.
- Permit one open thread at a time and multiple sequential loops.
- On response, restore the same team and Analyst assignment and create the next
  Analyst production task.
- Expose full messages only to the Customer, assigned Analyst and authorised Team
  Manager. Routing trackers receive state and timing metadata only.
- Reconcile partial database or Camunda failure without inventing a response or
  duplicating a task.

## Consequences

Clarification becomes an auditable production activity without adding another
approval stage. Deployment and smoke tests must cover both process versions until
all older instances have ended.

## Rejected alternatives

- Reuse intake clarification: it would incorrectly return work to JIOC.
- Store a free-text progress note only: it gives the Customer no actionable task
  and cannot model response state.
- Contact the Customer offline: loses history, access control and service timing.
