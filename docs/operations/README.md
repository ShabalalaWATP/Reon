# Operations runbooks

Status: current operational index
Last reviewed: 18 August 2026

These runbooks describe bounded procedures for the synthetic local topology and
decision frameworks for a future connected service. They do not authorise real
data, prove production readiness or replace a dated acceptance record.

## Choose the runbook

| Need | Runbook | Use it when |
|---|---|---|
| Inspect retention, create a database backup, rehearse restore or repair analytics | [Backup, restore and maintenance](BACKUP_RESTORE_AND_MAINTENANCE.md) | The exact database identity, operator authority, target and evidence location are known |
| Propose, review, activate or reverse routing configuration | [Configuration and routing](CONFIGURATION_AND_ROUTING_RUNBOOK.md) | PostgreSQL, Camunda, configuration integrity and the independent worker are ready |
| Triage, contain and recover a service incident | [Support and incident](SUPPORT_AND_INCIDENT_RUNBOOK.md) | An incident owner and severity have been assigned and evidence can remain content-free |
| Plan or exercise joined service recovery | [Business continuity and disaster recovery](BUSINESS_CONTINUITY_AND_DISASTER_RECOVERY.md) | Accountable owners have selected recovery objectives, dependencies and an isolated target |

## Common prerequisites

- Start local Compose with `pwsh -File ./scripts/start-local.ps1`, not plain
  `docker compose up`, so the BPMN is inspected, deployed when absent and
  attested.
- Confirm `http://127.0.0.1:8000/ready` reports `ready` before a routine
  workflow-changing procedure. Liveness alone is insufficient.
- Use the exact database identity named by the procedure. Runtime, migration,
  backup, maintenance and Camunda roles are not interchangeable.
- Keep passwords, connection strings, audit keys, cookies, Customer identity,
  request content and service products out of commands, screenshots and
  evidence.
- Use PowerShell 7.4. Backup and restore additionally require PostgreSQL 17
  client tools, and host-run Python commands require the locked `uv` environment.
- Resolve the current maintenance-role `CONNECT` omission and restore-helper URL
  incompatibility before claiming retention/legal-hold apply or current-head
  restore evidence from a fresh local stack.

## Procedures versus assurance

A procedure says what an authorised operator should do. Assurance proves what a
named candidate actually did in a dated environment. Passing a command locally
does not update an acceptance state by itself.

Store immutable or dated results under [assurance](../assurance/README.md) only
when the relevant exercise really ran and the evidence identifies the candidate,
environment, time, owner and result without sensitive content. Production use
remains governed by the [production gates](../deployment/PRODUCTION_GATES.md),
the [acceptance record](../assurance/ACCEPTANCE_RECORD.md) and the
[enterprise readiness gap register](../ENTERPRISE_READINESS_GAP_REGISTER.md).
