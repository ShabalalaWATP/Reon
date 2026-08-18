# Recovery evidence

## Current worker and analytics recovery verification, 18 August 2026

The maintainability candidate connects recovery paths that were previously
implemented only as internal functions. The operator maintenance interface now
exposes:

```powershell
uv run --directory apps/api python -m mist_service.maintenance `
  rebuild-analytics --request-limit 1000
uv run --directory apps/api python -m mist_service.maintenance `
  replay-operational-analytics `
  --start 2026-08-17T00:00:00+00:00 `
  --end 2026-08-18T00:00:00+00:00 `
  --source-limit 1000
```

Projection rebuild refuses limits outside 1 to 5,000 and fails before changing
projection state when the complete source set exceeds the selected limit.
Operational replay requires an explicit timezone-aware interval and a bounded
source count. It uses stable opaque source keys and insert-once facts, so retry
does not rewrite or duplicate prior facts. Analytics definition metadata is
persisted by key and version and must match the code-owned label, description,
unit and active state. A change without a version increment fails closed.

Notification projection recovery now processes each event in its own
transaction. A failed event receives content-free failure state and bounded
retry delay, later events in the batch remain eligible for repair, and an
aggregate exception makes durable worker job accounting record the unsuccessful
iteration. Cancellation is propagated and is not misreported as an ordinary
event failure.

A 21-test focused selection covering the worker-accounting and analytics-
definition corrections passed, followed by the complete 1,410-test backend
suite with 13 environment-specific skips. This is source and automated recovery
evidence. No fresh live worker-kill, large-dataset analytics rebuild, joined
multi-store restore or target-environment disaster-recovery rehearsal was run on
18 August, so the corresponding detailed recovery gates remain open.

## Camunda interruption

Recorded on 7 August 2026 using the local PostgreSQL and Camunda topology.
Camunda was stopped, a real Customer request was committed, and request
`SR-2026-05ADF192` remained in `ROUTING_PENDING` without an invented task.

The exercise exposed retry exhaustion that was too aggressive for a useful
outage. Default workflow-start and workflow-command attempts were increased from
5 to 30 with capped 30-second delay, covering approximately 13 minutes. A narrow
recovery command was added for an exact failed request:

```powershell
uv run --directory apps/api python -m mist_service.maintenance `
  workflow-recovery --request-id <uuid>
uv run --directory apps/api python -m mist_service.maintenance `
  workflow-recovery --request-id <uuid> --apply `
  --confirm REQUEUE_FAILED_WORKFLOW
```

The dry run made no change. The confirmed operation requeued only failed
commands, cleared the recorded workflow error and appended a content-free
`workflow_recovery_queued` history event. After Camunda restart, exactly one
`TRIAGE_REVIEW` task appeared and the operational snapshot returned zero backlog,
failed commands, projection errors and alerts.

## PostgreSQL interruption

PostgreSQL was stopped while the API remained up. The readiness path originally
attempted session membership synchronisation and returned an unsafe 500. It now
uses a raw read-only readiness session, catches connection-level and SQLAlchemy
failures, and returned a controlled 503 document with database unavailable and
workflow available. Readiness returned to healthy within seconds of database
restart. The recovered Camunda task remained unique.

## Restore and targets

The separate clean PostgreSQL restore rehearsal is recorded in
`docs/assurance/MIGRATION_AND_RESTORE_EVIDENCE.md`. It completed restore and
integrity verification in 1.22 seconds. These interruption exercises completed
inside the 15-minute dependency-recovery target with no lost committed request,
duplicate task or invented transition.

## Expanded-capability rehearsal, 8 August 2026

The PostgreSQL-backed Camunda 8.9.14 local topology completed both the JOCK,
ACSA-B Ops and SSG Team path, including two clarification loops, and the SYGOC,
Nimbus Ops and Beacon Team path. Both process instances reached `COMPLETED` and
business-ID uniqueness remained enforced.

Camunda was then stopped while the API remained available. Readiness returned a
controlled 503 with workflow unavailable. Camunda restarted and readiness
returned to `ready` in 23.24 seconds. PostgreSQL was independently stopped;
readiness returned a controlled 503 with database unavailable, then recovered in
14.46 seconds. After each interruption, process instance
`2251799813687059` retained its exact key and `COMPLETED` state.

The first application claim immediately after restart received a transient 503.
The durable outbox reconciled it without duplication; a subsequent complete
application journey released `SR-2026-771CE3AE` through SYGOC, Nimbus Ops and
Beacon Team and verified the Customer download. The final health snapshot showed
zero command backlog, failed commands, workflow task errors, workflow instance
errors or alerts.

A long-lived QA database with pre-sealing configuration evidence correctly
failed readiness after the current image was applied. It was not rewritten or
backdated. A separate empty target project then migrated to 0018, seeded through
the governed configuration lifecycle, received explicit workflow availability
attestation and completed `SR-2026-2E06B694` through the alternative route. A
second request returned the current route as `CRIOC [CRIOC]` and exactly `JOCK`,
`SYGOC` and `MYGOC` as direct destinations. The isolated containers, networks and
volumes were removed after the rehearsal; the long-lived QA data was retained.

## SOLID and Secure by Design boundary rehearsal, 11 August 2026

Forty-one focused restore verification, Camunda recovery, cancellation,
workflow-command dispatch and operational-snapshot tests passed before the live
exercise.

The retained local Camunda service was stopped without deleting its container
or volumes. `/ready` returned HTTP 503 with `workflow: unavailable` while the
database, configuration and maintenance checks remained `ok`. `docker compose
up -d --wait --wait-timeout 90 orchestration` returned the service to healthy
and full API readiness in 42.48 seconds.

PostgreSQL was then stopped independently. `/ready` returned HTTP 503 with the
database, configuration and maintenance checks unavailable while workflow
remained `ok`. `docker compose up -d --wait --wait-timeout 90 postgres` returned
PostgreSQL and full API readiness in 11.80 seconds.

No volume, request or account data was removed. These local dependency
interruptions prove controlled failure and recovery inside the 15-minute local
target. They do not replace a current coordinated production backup/restore or
target-environment disaster-recovery rehearsal.
