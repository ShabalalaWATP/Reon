# Backup, restore and maintenance

Status: implemented inspection and backup controls with named local limitations
Last reviewed: 18 August 2026

## Database identities

Local Compose defines five separate PostgreSQL service identities:

- `APP_DATABASE_USER` owns the application schema and is available only to the
  one-shot migrator;
- `APP_RUNTIME_DATABASE_USER` runs the API with ordinary data access but cannot
  alter the schema or mutate append-only evidence;
- `APP_BACKUP_DATABASE_USER` has read-only access for `pg_dump`;
- `APP_MAINTENANCE_DATABASE_USER` is intended for approved retention and
  legal-hold jobs with narrowly scoped table permissions; and
- `CAMUNDA_DATABASE_USER` is confined to the separate Camunda database.

The maintenance/disposal identity is not the API runtime, schema owner or
Platform Administrator. Grant only the bounded permissions defined by the
approved retention procedure. Before an apply operation, configure
`MAINTENANCE_DATABASE_URL`, `MAINTENANCE_OPERATOR_SUBJECT`,
`MAINTENANCE_DISPOSAL_AUTHORITY=RETENTION_DISPOSAL` and
`MAINTENANCE_LEGAL_HOLD_AUTHORITY=LEGAL_HOLD_ADMIN` in the job environment.

All passwords must differ from one another, the bootstrap password and the demo
login password. Do not place connection strings in command history or evidence.

### Current fresh-Compose limitation

The PostgreSQL bootstrap creates the maintenance role and the migrator grants
its schema and table permissions, but it does not grant that role database-level
`CONNECT`. Consequently a fresh Compose database cannot currently execute these
intended commands:

```powershell
uv run --directory apps/api mist-maintenance retention --apply `
  --confirm APPLY_RETENTION
uv run --directory apps/api mist-maintenance legal-hold apply `
  --target-type REQUEST --target-id <uuid> --reason-code <approved-code>
uv run --directory apps/api mist-maintenance legal-hold release `
  --target-type REQUEST --target-id <uuid>
```

Do not treat these as local evidence until database provisioning grants the
separate role `CONNECT` and the commands pass PostgreSQL integration tests. Do
not grant disposal or legal-hold mutation rights to the API runtime as a
workaround. This is a production-readiness blocker.

### Current command-safety limitations

The maintenance command path is not approved for non-loopback or real-data use:

- `MAINTENANCE_DATABASE_URL` is copied into the database engine without the
  production URL validation applied to `DATABASE_URL`. The runtime does not yet
  enforce `postgresql+asyncpg`, server identity verification or the approved CA
  for this privileged connection.
- Retention preview reads `DATABASE_URL`, while apply reads
  `MAINTENANCE_DATABASE_URL`. The static `APPLY_RETENTION` text is not bound to a
  database fingerprint, policy version, preview counts, operator or expiry. A
  preview therefore never authorises an apply operation.
- Legal-hold release accepts only target type and ID. It has no mandatory release
  reason, readback or expiring target-, database- and operator-bound
  confirmation.

These are `NOT IMPLEMENTED` safety controls, not operator discretion. Keep
retention apply and legal-hold release disabled until the runtime enforces them
and two-database, wrong-target, stale-confirmation and transport-negative tests
pass. Consider independent approval for hold release. The missing fresh-stack
`CONNECT` grant is defence in depth by accident, not the intended control.

## Retention

For the local stack, inspect eligible counts without changing data through the
API container's runtime connection:

```powershell
docker compose exec --no-TTY api python -m mist_service.maintenance retention
```

This is a diagnostic preview of the runtime database only. It is not a safe
approval token for the separate maintenance target. The currently exposed apply
interface is shown for implementation traceability, but must not be run against
real or non-loopback data:

```powershell
uv run --directory apps/api mist-maintenance retention --apply `
  --confirm APPLY_RETENTION
```

Before enablement, preview and apply must use the same separately authorised
maintenance target and an expiring confirmation bound to a content-free database
fingerprint, policy version, exact counts, operator and expiry. The interface is
also blocked on fresh Compose by the missing `CONNECT` grant described above.

The command deletes at most 1,000 eligible rows per class and emits counts only.
Active legal holds suppress every matching candidate. Completed request and
managed-product candidates are fail-closed until the approved adapter can erase
database metadata and private object storage together. Request events contain
workflow messages and details and are therefore content-bearing, despite their
audit purpose. They inherit the request hold and disposal decision.

The versioned schedule covers expired sessions and drafts, decided account
requests, completed requests and activity, feedback, closed clarifications,
notifications, managed products, product access events and content-free security
events. Policy changes require owner and legal approval, a new policy version and
a dry run. Legal holds are applied and released only through `LEGAL_HOLD_ADMIN`,
never an ordinary application role.

Accepted legal-hold target types are `ACCOUNT_REQUEST`, `ACCESS_EVENT`,
`ACTIVITY`, `CLARIFICATION`, `FEEDBACK`, `IDENTITY`, `NOTIFICATION`, `PRODUCT`,
`REQUEST` and `SECURITY_EVENT`. Apply requires a non-empty approved reason code.
Safe release is not implemented: do not release a hold until the command requires
readback, a release reason or change reference and an expiring confirmation bound
to the exact hold, operator and database. Both actions are also blocked on a
fresh Compose database by the limitation above.

## Backup

Install PostgreSQL 17 client tools (`pg_dump`, `pg_restore` and, for restore,
`psql`) plus PowerShell 7.4. The backup script deliberately requires
`pg_restore` so it can inspect the custom archive immediately. An older
`pg_dump` must not be used against the PostgreSQL 17.10 server.

Set `MIST_BACKUP_DATABASE_URL` for the read-only backup identity. For any host
other than the exact local exceptions `localhost`, `127.0.0.1` and `[::1]`, the
URL must include `sslmode=verify-full` and `sslrootcert` pointing to the same
existing CA bundle named by `MIST_POSTGRES_APPROVED_SSL_ROOT_CERT`.

Load a separately controlled, random key of at least 32 bytes as base64 in
`MIST_BACKUP_INTEGRITY_KEY_BASE64`. Keep it in the operational secret store,
separate from backup storage and the database credentials. For example, generate
the value inside the approved secret-management boundary, not in repository
configuration. Then run:

```powershell
pwsh -File scripts/backup-postgres.ps1 -OutputDirectory C:\mist-backups
```

Retain the `.dump` and matching `.sha256.json` together in controlled storage.
A file is not a valid backup merely because `pg_dump` exited successfully. The
script also validates the catalogue and records an HMAC-authenticated checksum,
filename and creation timestamp. Loss of the separate integrity key makes restore
verification impossible, so protect and recover it under the operational key
management procedure.

Backups are immutable copies and do not receive row-level deletion. Retain each
backup for the period approved in the target environment, then expire the whole
backup and manifest through the storage lifecycle. This repository does not set
or prove a production backup-retention period. A legal hold pauses expiry for
the complete affected backup set. Restoring an older backup must run retention
before service is opened and must not reintroduce disposed data into the live
database. Record lifecycle expiry and restore-time disposal as content-free
operational evidence.

Audit HMAC rotation uses `AUDIT_HMAC_ACTIVE_KEY_ID` and a JSON
`AUDIT_HMAC_KEYRING`. Add the new key, retain every old key referenced by stored
events, change the active ID, verify request and administration chains, then
deploy. Never remove a verification key until every referencing event and backup
has lawfully expired. Losing an old key makes its historic chain unverifiable.

Current Compose does not forward `AUDIT_HMAC_ACTIVE_KEY_ID` or
`AUDIT_HMAC_KEYRING`. Stop if the target runtime has no explicit transport for
both settings. Do not report a Compose rotation until that transport is
implemented and pre-change plus post-change verification proves every live and
restored chain with the retained keyring.

## Isolated restore rehearsal

Create a new empty PostgreSQL database with a dedicated restore owner. Set
`MIST_RESTORE_DATABASE_URL` for that database, applying the same remote TLS and
approved CA-path rule. Load the original backup integrity key and every audit
HMAC key referenced by restored events from their separate secret stores, then
run:

```powershell
pwsh -File scripts/restore-postgres.ps1 `
  -BackupFile C:\mist-backups\mist-YYYYMMDDTHHMMSSZ.dump `
  -EvidenceDirectory .local-evidence\restore `
  -Confirmation RESTORE_ISOLATED_DATABASE
```

The verifier defaults to current Alembic head
`0049_legacy_product_cleanup`. For a different immutable candidate, pass its
exact reviewed revision with `-ExpectedRevision`; never weaken the comparison.

The script authenticates the manifest and checksum before connecting. It refuses
a target containing any public table, then verifies archive structure, Alembic
revision, content-free counts and both audit chains.
Afterwards, reconcile restored active requests with Camunda before considering a
recovery usable.

The current restore script has an open transport defect: its libpq service-file
builder accepts only `postgres://` or `postgresql://`, while the Python
`verify-restore` step reuses the same value as `DATABASE_URL` and requires the
async `postgresql+asyncpg://` scheme. No one URL satisfies both consumers. The
command above must therefore not be reported as a successful current-head
restore rehearsal until the script is fixed and the full empty-target exercise
passes. It never authorises restoring over a populated target.

## Operational snapshot

For local Compose, run the content-free database snapshot through the API
container:

```powershell
docker compose exec --no-TTY api python -m mist_service.maintenance health-snapshot
```

`scripts/check-operational-health.ps1` also checks API readiness and validated
backup age, but it host-runs the same CLI. Before invoking it for local Compose,
override `DATABASE_URL` with a host-reachable runtime URL at
`127.0.0.1:${POSTGRES_HOST_PORT}`. The root `.env` value uses Compose DNS
`postgres` and is not host-reachable. Follow alert handling and escalation in
[`SUPPORT_AND_INCIDENT_RUNBOOK.md`](SUPPORT_AND_INCIDENT_RUNBOOK.md).

## Analytics recovery

Rebuild the content-free request projection after a projection-version change or
a verified projection incident:

```powershell
docker compose exec --no-TTY api python -m mist_service.maintenance rebuild-analytics `
  --request-limit 1000
```

The command is transactional and idempotent. It refuses an invalid limit, a
limit above 5,000, or a store containing more requests than the supplied limit.
Increase the limit only after checking the source count and maintenance window.

Replay missing append-only operational facts for an explicit time-zone-aware
window:

```powershell
docker compose exec --no-TTY api python -m mist_service.maintenance replay-operational-analytics `
  --start 2026-08-17T00:00:00+00:00 `
  --end 2026-08-18T00:00:00+00:00 `
  --source-limit 1000
```

The replay inserts by stable source key, so repeating the same window does not
duplicate facts. It accepts at most 5,000 source records and a 366-day
time-zone-aware window. Both commands use the ordinary application database
connection because the restricted disposal identity cannot rewrite projections
or append analytics facts.
