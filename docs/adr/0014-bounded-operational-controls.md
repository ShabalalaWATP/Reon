# ADR 0014: Bounded operational controls

## Status

Accepted for implementation on 7 August 2026. Stakeholder ownership remains a
pilot sign-off item.

## Decision

Use an application-owned, allow-listed retention job with dry-run as the default,
an exact apply confirmation, bounded batches and append-only count evidence. Do
not implement a generic table purge facility.

Use PostgreSQL native custom-format backup and restore tools behind checked
PowerShell operator scripts. A restore target must be empty and isolated. Verify
the Alembic revision, core counts and audit integrity after restore.

Keep monitoring content-free and treat PostgreSQL plus Camunda reconciliation as
one recovery boundary. Source-controlled BPMN and configuration are restored from
the reviewed application baseline, not from arbitrary engine exports.

Use separate PostgreSQL identities for schema migration, application runtime and
backup. The one-shot migrator disposes the owner credential before the API
starts. The runtime role receives ordinary application data permissions but
cannot update, delete or truncate append-only audit tables. The backup identity
is read only.

## Consequences

- Business and audit history cannot be removed by the v1 retention job.
- Draft, session and successfully dispatched command storage is controlled without
  creating an unrestricted deletion primitive.
- Restore is deliberately non-destructive to populated databases.
- A later approved information policy may add end-to-end request deletion through
  a new ADR, migration design and threat-model review.
