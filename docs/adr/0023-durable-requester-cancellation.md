# ADR 0023: Durable requester cancellation

## Status

Accepted.

## Context

A Customer must be able to stop an active service request at any human-led stage.
PostgreSQL owns the requester-facing state and audit history, while Camunda owns
the process instance and active task lifecycle. Calling Camunda synchronously
inside the request transaction would hold database locks during external I/O and
could leave one system changed when the other fails.

## Decision

Cancellation is accepted through an owner-only FastAPI use case that locks and
versions the request. In one transaction it sets the request to `CANCELLED`,
closes local tasks and planning records, appends the hash-linked reasoned event,
and either suppresses a process start that has not left PostgreSQL or writes an
idempotent `CANCEL_PROCESS` outbox command.

A dedicated fenced worker dispatches `CANCEL_PROCESS` through the existing
workflow-engine port. It proves uncertain or repeated calls by querying the exact
process instance and accepts only `TERMINATED` as cancellation success. If a
process start was already in flight, start projection records its key without
reopening application work, then the cancellation worker terminates it.

The browser receives the terminal PostgreSQL projection immediately. It does not
call Camunda and does not wait for eventual engine convergence.

## Consequences

- Request queues, the Customer register and statistics close immediately.
- Camunda I/O remains outside product transactions and is recoverable.
- Cancellation requires an additional worker path and operational retry state.
- Existing request history remains immutable and retains the cancellation reason.
- A cancelled request cannot be reopened in the MVP.
