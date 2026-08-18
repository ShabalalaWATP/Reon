# Operational readiness specification

Status: current local-pilot contract; production acceptance remains open. Last
reviewed 18 August 2026.

## Purpose

Provide safe, reproducible operating controls for the pilot without turning the
application into a production deployment. Controls must remain content-minimised,
fail closed, and be independently verifiable.

## Retention policy v2

The scheduled job runs in dry-run mode unless an operator supplies the exact
application confirmation token. Disposal of business content also requires a
separately authorised disposal identity. One run processes at most 1,000 records
per data class so locks and transactions stay bounded. Active legal holds exclude
their exact records from both disposal and identity anonymisation.

| Data class | Retention action | Period | Rationale |
| --- | --- | ---: | --- |
| Expired or revoked sessions | Delete | 30 days after expiry or revocation | Authentication artefacts have no enduring business value |
| Unsubmitted Customer drafts | Delete | 90 days after last update | Remove abandoned content while allowing practical resumption |
| Successfully sent workflow-outbox commands | Delete | 30 days after send | Business history remains in request events and workflow projections |
| Failed or pending workflow commands | Preserve | Indefinite until resolved | Required for recovery and diagnosis |
| Resolved account requests | Delete | 365 days after review | Removes expired access-request metadata under legal-hold control |
| Completed, closed or cancelled requests and their dependent records | Report as eligible; do not yet delete | 2,555 days after last update | Coordinated request and object disposal requires the approved transactional storage adapter |
| Team and work-package activity | Delete | 730 days after event | Bounded operational history after the accountability period |
| Feedback and closed clarification threads | Delete | 730 days after creation or closure | Applies the approved content lifecycle while preserving open work |
| Notification records | Delete | 180 days after occurrence | Removes expired action-delivery metadata |
| Product packages | Report as eligible; do not yet delete | 2,555 days after last update | Product metadata and stored objects must be disposed atomically through the production adapter |
| Product-access and security events | Delete | 730 days after event | Retains a bounded investigation and access-accountability window |
| Inactive identities | Anonymise bounded identity and profile fields | 730 days after last update | Preserves referential history without retaining reusable account data |
| Request events, conversations and administration audit records | Preserve with their owning record | No independent deletion | Prevents orphaned or selectively rewritten accountable history |

Dry-run and applied results contain class counts and policy metadata only. They
must never contain identifiers, request text, Customer details or credentials.
Applied runs are recorded as append-only operational evidence in the same
transaction as the deletion. If completed-request or product candidates exist,
apply fails closed until the coordinated storage-disposal adapter is available.

## Backup and restore

- PostgreSQL backups use custom format, no ownership or ACL export, SHA-256
  checksum, restrictive output permissions and an atomic final filename.
- A backup is not accepted until `pg_restore --list` validates it.
- Restore requires an explicit confirmation and an empty, isolated target
  database. It never cleans or overwrites a populated target.
- Restore verification checks the schema revision, core row counts and both
  tamper-evident audit chains without displaying content.
- Camunda configuration and BPMN are source-controlled. PostgreSQL and Camunda
  recovery are rehearsed together because database restoration alone cannot
  prove workflow consistency.

## Observability and support

Operational telemetry is limited to health, dependency state, command backlog,
oldest pending age, projection freshness, backup age, latency and error counts.
It excludes request fields, user identifiers, tokens and task payloads. Alert
thresholds and incident ownership are defined in the support runbook.

## Acceptance criteria

1. Dry-run reports eligible counts without changing the database.
2. Apply refuses missing or incorrect confirmation, deletes only eligible rows,
   processes a bounded batch and records append-only counts.
3. Ineligible and unresolved records remain untouched under concurrency.
4. Backup creation, validation, checksum and clean restore are scripted and
   rehearsed on PostgreSQL.
5. Restore verification detects revision, row-count or audit-integrity failure.
6. Recovery, rollback, alert and escalation procedures have named pilot owners or
   an explicitly recorded owner gap.
