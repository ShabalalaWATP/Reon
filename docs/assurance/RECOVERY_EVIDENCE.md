# Recovery evidence

## Camunda interruption

Recorded on 7 August 2026 using the local PostgreSQL and Camunda topology.
Camunda was stopped, a real Customer request was committed, and request
`SR-2026-05ADF192` remained in `ROUTING_PENDING` without an invented task.

The exercise exposed retry exhaustion that was too aggressive for a useful
outage. Default workflow-start and workflow-command attempts were increased from
5 to 30 with capped 30-second delay, covering approximately 13 minutes. A narrow
recovery command was added for an exact failed request:

```powershell
uv run --directory apps/api python -m istari_service.maintenance `
  workflow-recovery --request-id <uuid>
uv run --directory apps/api python -m istari_service.maintenance `
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
