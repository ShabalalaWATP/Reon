# ADR 0020: Fenced workers and external-I/O transaction boundaries

Status: accepted
Date: 8 August 2026

## Context

The API originally hosted its maintenance loop in every process. Scheduled team
membership projection also ran at the start of every ordinary HTTP database
session. Human task dispatch and managed upload/scan paths performed external
calls while row locks and transactions were open. These behaviours are correct
at small scale but couple request latency, database capacity and replica count to
maintenance and dependency latency.

## Decision

1. Run maintenance in a separate `mist-worker` process.
2. Store named maintenance job leases and heartbeat state in PostgreSQL.
3. Use owner plus monotonically increasing generation as the fencing token.
4. Retain per-row outbox leases for parallel workflow dispatch.
5. Split human command execution into lease, external execution and fenced
   finalisation transactions.
6. Add an upload-intent operation lease for scanner and promotion work.
7. Perform upload body/storage work and download streaming outside database
   transactions.
8. Reauthorise and compare optimistic versions during every finalisation.
9. Use database keyset pagination rather than offset pagination or broad
   in-memory collection.

## Why this design

Database leases are portable across local PostgreSQL and managed PostgreSQL
services, recover after process death and provide an auditable fencing token.
They avoid a new queue dependency while preserving the transactional outbox.
Separating the three phases ensures slow Camunda, scanner or storage calls do
not consume row locks or idle-in-transaction connections.

Keyset pagination keeps work proportional to page size and remains stable as
newer rows arrive. It matches the existing action and notification contracts.

## Consequences

- The local topology gains a worker service and the API no longer starts a
  background loop.
- Readiness depends on a recent durable worker heartbeat when maintenance is
  required.
- A worker can repeat an idempotent external call after lease expiry. Only the
  current generation may project the outcome.
- Product scan/promotion adapters must be idempotent for their deterministic
  object keys.
- Cursor response contracts change additively and clients must request older
  pages explicitly.
- Database migrations add worker state, product operation lease columns and
  composite indexes.

## Alternatives rejected

- Running one loop per API replica retains lifecycle coupling and makes replica
  scaling alter maintenance pressure.
- Holding row locks during external calls prevents competing work but converts
  dependency latency into database contention.
- Offset pagination becomes progressively slower and can skip or duplicate rows
  when operational data changes.
- Adding a message broker now would create another operational dependency
  without removing the need for fencing and idempotent projection.

## Out of scope

Concurrent WIP-limit serialisation is intentionally excluded from this decision.
