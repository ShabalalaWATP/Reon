# Business continuity and disaster recovery framework

Status: decision framework, not an accepted production plan
Last reviewed: 18 August 2026

## Purpose and scope

This framework covers PostgreSQL, Camunda, private product objects and scan
evidence, the command outbox, projections, configuration snapshots, request
pins, audit evidence and deployment artefacts. It does not assign an RTO, RPO or
recovery owner. Those are accountable business decisions and remain production
blockers.

## Service priorities

| Priority | Capability | Safe degraded position |
|---|---|---|
| 1 | Authentication, authorisation and Customer product protection | Fail closed |
| 2 | Authoritative request, configuration and audit integrity | Stop affected mutations and preserve evidence |
| 3 | Human workflow position and claimed tasks | Queue durable commands; never invent completion |
| 4 | Customer tracking and operational queues | Read-only or unavailable with honest freshness |
| 5 | Search, notifications, statistics and planning projections | Degraded, never authoritative |

## Invocation decision record

Before production, owners must approve and record:

- incident commander, recovery lead, security lead and business decision maker;
- RTO and RPO by capability, plus maximum tolerable outage and data loss;
- invocation, stand-down, communications and regulatory-notification authority;
- backup frequency, immutability, encryption, key custody, geographic location
  and retention;
- manual intake, product dissemination and customer-communication fallback;
- dependency contacts and support entitlements for hosting, PostgreSQL, Camunda,
  object storage and malware scanning; and
- exercise frequency, observer, evidence retention and remediation ownership.

## Recovery sequence

1. Contain the incident and stop unsafe new intake or product release.
2. Select an independently verified recovery point and create an empty,
   isolated target. Never restore over a live schema.
3. Restore PostgreSQL and verify migration revision, expected counts, request
   ownership, audit chains and configuration evidence.
4. Restore or reconnect private objects, compare object inventory and checksum
   with package and scan metadata, and keep unmatched items quarantined.
5. Reconcile Camunda process identity and task state with durable commands and
   request pins. No projection may create authoritative workflow success.
6. Rebuild action, notification, organisation, planning and analytics
   projections idempotently from authoritative sources.
7. Prove current configuration digest, organisation closure, candidate groups,
   approved workflow identity and representative new and in-flight routes.
8. Obtain named security, operational and business approval before reopening.

## Exercise scenarios

- unavailable primary PostgreSQL with point-in-time recovery;
- corrupt or incomplete backup;
- lost Camunda search/index state with authoritative engine state retained;
- PostgreSQL and Camunda recovery points that do not initially agree;
- missing, additional or malicious product objects after restore;
- configuration digest mismatch or corrupted active pointer;
- outbox interruption during route or dissemination; and
- loss of a region, identity provider, scanner or key-management dependency.

Each exercise records timestamps, chosen recovery point, commands, environment,
integrity results, deviations, residual risk, owner and due date. Synthetic data
must be used until the information-handling model is approved.

## Current evidence and limitations

Local PostgreSQL backup tooling, integrity checks, fail-closed readiness and
controlled dependency recovery exist. Historical migration evidence is in
[`MIGRATION_AND_RESTORE_EVIDENCE.md`](../assurance/MIGRATION_AND_RESTORE_EVIDENCE.md),
but the current restore script cannot complete its Python verification because
its libpq and async-SQLAlchemy consumers require incompatible URL schemes. The
current fresh Compose bootstrap also omits the maintenance role's database-level
`CONNECT` grant. There is no accepted production RTO/RPO, current-head restore
rehearsal, immutable backup platform, point-in-time recovery rehearsal,
multi-store recovery exercise, on-call rota or signed continuity plan.
