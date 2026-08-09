# Support and incident runbook

## Pilot ownership

Named people must be entered in the signed pilot record before service launch.
Until then, the role owner is accountable and the ownership status is explicitly
`PENDING NOMINATION`.

| Responsibility | Pilot role owner | Named owner |
| --- | --- | --- |
| Service and user support | Product owner | PENDING NOMINATION |
| Application incident commander | Technical lead | PENDING NOMINATION |
| PostgreSQL backup and recovery | Operational owner | PENDING NOMINATION |
| Camunda recovery and reconciliation | Workflow owner | PENDING NOMINATION |
| Security incident decision | Security owner | PENDING NOMINATION |
| Customer communications | Product owner | PENDING NOMINATION |

Supported pilot hours are Monday to Friday, 08:00 to 18:00 Europe/London,
excluding public holidays. P1 security or data-loss concerns use the agreed
out-of-hours escalation channel once named in the pilot record.

## Severity and targets

| Severity | Example | Acknowledge | Stabilise or escalate |
| --- | --- | ---: | ---: |
| P1 | Suspected data exposure, unrecoverable loss, broad authentication failure | 15 min | 30 min |
| P2 | Workflow stopped, database unavailable, release path unavailable | 30 min | 60 min |
| P2 | Active configuration has no complete route, wrong branch is broadly selectable, or hierarchy reconciliation fails | 30 min | 60 min |
| P3 | One role or non-critical workspace impaired | 4 supported hours | 1 supported day |
| P4 | Cosmetic issue or low-impact request | 1 supported day | Planned backlog |

## Content-free alert thresholds

- readiness database or Camunda unavailable for two consecutive one-minute checks;
- any failed workflow command, any workflow projection error, or oldest actionable
  command over five minutes;
- analytics projection not ready or more than ten minutes old;
- no validated PostgreSQL backup within 26 hours;
- API five-minute error rate above 2 per cent, p95 above two seconds for ten
  minutes, or p99 above four seconds;
- retention apply has not succeeded within eight days.

The local pilot check is `scripts/check-operational-health.ps1`. A production
monitor must call equivalent controls from a private monitoring plane.

## Triage sequence

1. Assign an incident identifier and record time, severity, owner and affected
   capability. Do not copy request content into the incident record.
2. Check `/health`, `/ready` and the content-free maintenance health snapshot.
3. Check PostgreSQL availability, Camunda availability, command backlog,
   projection errors and latest validated backup age.
4. Contain security risk first. Revoke affected accounts or stop ingress when
   justified. Preserve audit and command evidence.
5. Recover using the narrowest reversible action. Reconcile before retrying.
6. Validate representative Customer and staff journeys, then close or downgrade.
7. Record root cause, timeline, evidence, residual risk and prevention action.

Configuration and routing incidents use
[`CONFIGURATION_AND_ROUTING_RUNBOOK.md`](CONFIGURATION_AND_ROUTING_RUNBOOK.md).
Do not directly repair the active hierarchy in PostgreSQL or Camunda. Contain
risk, preserve in-flight pins and apply an independently approved superseding
change.

## Recovery and rollback

- Application rollback uses the last reviewed source and image baseline. Database
  rollback is never assumed safe after a forward migration.
- Stop application writes before database restore. Restore only into an empty,
  isolated database, run the verification command, then reconcile every active
  request with Camunda before switching traffic.
- If Camunda was interrupted without database loss, restart it, run readiness and
  reconciliation, then allow bounded command retries. The default 30 attempts
  use capped delay and cover approximately 13 minutes. Never fabricate task
  state.
- If an exact request exhausted its workflow retries during a longer outage,
  inspect it first with `python -m istari_service.maintenance workflow-recovery
  --request-id <uuid>`. Requeue only after Camunda is healthy, using `--apply
  --confirm REQUEUE_FAILED_WORKFLOW`. The command refuses non-failed work,
  rechecks state in a transaction and appends a content-free recovery event.
- After recovery, prove the expected current task exists exactly once. Confirm
  the failed-command, pending-command, projection-error and alert counts return
  to zero before closing the incident.
- If PostgreSQL was interrupted without loss, restore connectivity, check audit
  integrity, command backlog and projections, then resume maintenance.
- If both stores were lost, restore PostgreSQL and the reviewed Camunda
  deployment, reconcile source-controlled BPMN version and active instances, and
  require operational and product-owner approval before reopening.

## Safe diagnostics

Permitted evidence is correlation ID, route template, status code, latency,
dependency health, aggregate counts, command status and age, process/task keys,
software versions and timestamps. Do not collect request text, output text,
Customer identity, cookies, CSRF tokens, passwords, connection strings, audit
keys or Camunda payloads.
