# ADR 0003: Durable Human-Workflow Commands

## Status

Accepted, 6 August 2026.

## Context

PostgreSQL and Camunda cannot participate in one application transaction. Calling
Camunda before committing product state can strand an engine task when the API
process stops between the engine response and the database commit. Updating the
product first without a durable command can lose the requested human action.

Claim and completion are security-sensitive effects. A retry must not repeat an
action blindly, accept a stale actor or infer an engine result from a local error
flag.

## Decision

Represent every claim and completion as a durable workflow command:

1. In product transaction A, lock and revalidate the current task, request,
   actor, role, scope, assignment, status and request version.
2. Append an idempotent outbox command and move the projected task to
   `CLAIM_PENDING` or `COMPLETION_PENDING` in the same commit.
3. After transaction A commits, let the API and background maintenance use the
   same dispatcher. A short lease with a random generation token permits another
   dispatcher to recover an abandoned `PROCESSING` command. Every result update
   compares that token so a stale worker cannot overwrite a newer result.
4. Immediately before the engine call, lock and revalidate the immutable command
   against the current active account and product records.
5. On a confirmed Camunda result, atomically project the claim or transition,
   append the attributable audit event and mark the command sent in product
   transaction B.
6. On an ambiguous claim result, inspect the exact active Camunda task. Finalise
   only when its key and assignee prove the outcome. Project a valid competing
   claimant explicitly.
7. On an ambiguous completion result, require the expected next task, or the
   explicit terminal process state `COMPLETED`, before recovery advances the
   product. `TERMINATED` never proves that a human dissemination succeeded.
8. On a temporary engine failure, keep the action recorded, remove its actions
   from active queues and return a stable retry message. After bounded attempts,
   expose a support-owned error state instead of reopening the task.

Commands store business content only in the product database. Camunda receives
opaque request and identity identifiers plus the human-selected routing value.
Passwords, session identifiers, CSRF tokens, reasons and service product text are
never workflow variables.

Process starts use the request UUID as the business ID. Camunda business-ID
uniqueness is a deployment prerequisite, not an optional optimisation. Projection
reconciliation captures the expected request version, process key and status,
then locks and revalidates them before applying an engine observation.

## Consequences

Human actions survive API termination and workflow outages without pretending
the two systems share an ACID boundary. Competing or stale actions have one
observable winner. The design requires a maintenance dispatcher, leases,
idempotency constraints, reconciliation queries and explicit support handling.

The synchronous API can report success only after the product projection is
committed. A `503` may mean the command is safely recorded and will be retried,
so clients must refresh instead of submitting a replacement action.

## Verification

- Stop after transaction A and prove an expired lease resumes the command.
- Race a reclaimed worker against its expired predecessor and prove the stale
  result cannot change a successful command or request projection.
- Stop after the Camunda effect and prove task or process-state inspection
  reconstructs transaction B without repeating the human effect.
- Race two claimants and prove one assignment is projected.
- Disable or rescope an actor after transaction A and prove dispatch fails closed.
- Reject mismatched task keys, elements, process instances, statuses and request
  versions.
- Race reconciliation with a completed command and prove a stale engine snapshot
  cannot restore the previous task.
- Prove a terminated process cannot release or disseminate the product.
- Inject a lost process-start response and prove Camunda business-ID uniqueness
  leaves one process instance.
- Exhaust retries and prove the task remains visibly support-owned with no action
  controls.
- Assert that captured Camunda variables contain only the approved routing
  contract.
