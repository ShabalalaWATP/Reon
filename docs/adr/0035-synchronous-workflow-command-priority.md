# ADR 0035: Synchronous workflow command priority

## Status

Accepted, 14 August 2026.

## Context

Claim and completion handlers commit a durable PostgreSQL command before calling
Camunda. The API and maintenance worker previously treated a new command as
immediately eligible. A worker could lease and successfully project the command
between the API commit and its explicit dispatch. The API then observed no
claimable row and returned `503`, or an associated finalisation error, even though
the action had succeeded. Retrying that apparent failure was confusing and could
challenge idempotency boundaries.

## Decision

Give a new human-workflow command a five-second recovery availability delay.
Explicit dispatch by the API may claim an untouched command during that delay;
background maintenance honours the delay. Retry back-off is never bypassed after
the first attempt.

If explicit dispatch finds that another owner already holds the lease, it polls
the durable outbox for a bounded hand-off period. `SENT` is success, `FAILED` is a
confirmed rejection, and a command that remains pending or processing retains the
existing durable-retry response. Lease generation fencing and engine-side
reconciliation remain unchanged.

Final command validation and locked request-detail authorisation use PostgreSQL
`FOR NO KEY UPDATE` for the actor row. This continues to prevent account changes
during each authorisation decision but does not conflict with the `KEY SHARE`
locks taken when notification recipients reference that actor. Request detail
still locks the authorised request, so its object and visibility decision remain
stable for the response transaction. A detected PostgreSQL command deadlock is
retried once through the same idempotent command and reconciliation path before
returning the bounded workflow-unavailable response.

## Consequences

The normal request path no longer races maintenance for initial ownership. If the
API stops after committing the command, maintenance recovery begins within five
seconds plus its normal polling interval. The bounded hand-off also makes rolling
upgrades and commands created before this decision tolerant of an existing
worker lease.

This changes scheduling only. It does not make PostgreSQL and Camunda atomic, and
it does not permit a local projection to infer success without a `SENT` command.

## Verification

- Prove explicit dispatch can claim an untouched command before its recovery time.
- Prove background dispatch cannot claim that command before the recovery time.
- Prove a competing dispatcher that projects `SENT` is observed as success.
- Prove `FAILED`, retry-delayed and missing commands remain fail-closed.
- Prove both command and detail-read actor validation compile to the
  foreign-key-compatible PostgreSQL lock mode.
- Complete both configured organisational routes against concurrent API and
  maintenance processes.
