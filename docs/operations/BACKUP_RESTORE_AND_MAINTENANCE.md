# Backup, restore and maintenance

## Database identities

Local Compose uses five separate PostgreSQL service identities:

- `APP_DATABASE_USER` owns the application schema and is available only to the
  one-shot migrator;
- `APP_RUNTIME_DATABASE_USER` runs the API with ordinary data access but cannot
  alter the schema or mutate append-only evidence;
- `APP_BACKUP_DATABASE_USER` has read-only access for `pg_dump`;
- `APP_MAINTENANCE_DATABASE_USER` runs approved retention and legal-hold jobs
  with narrowly scoped permissions;
- `CAMUNDA_DATABASE_USER` is confined to the separate Camunda database.

The maintenance/disposal identity is not the API runtime, schema owner or
Platform Administrator. Grant only the bounded permissions defined by the
approved retention procedure. Before an apply operation, configure
`MAINTENANCE_DATABASE_URL`, `MAINTENANCE_OPERATOR_SUBJECT`,
`MAINTENANCE_DISPOSAL_AUTHORITY=RETENTION_DISPOSAL` and
`MAINTENANCE_LEGAL_HOLD_AUTHORITY=LEGAL_HOLD_ADMIN` in the job environment.

All passwords must differ from one another, the bootstrap password and the demo
login password. Do not place connection strings in command history or evidence.

## Retention

Preview eligible counts without changing data:

```powershell
uv run --directory apps/api istari-maintenance retention
```

Apply the approved policy only after reviewing the dry run:

```powershell
uv run --directory apps/api istari-maintenance retention --apply `
  --confirm APPLY_RETENTION
```

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

## Backup

Set `ISTARI_BACKUP_DATABASE_URL` for the read-only backup identity. For any host
other than the exact local exceptions `localhost`, `127.0.0.1` and `[::1]`, the
URL must include `sslmode=verify-full` and `sslrootcert` pointing to the same
existing CA bundle named by `ISTARI_POSTGRES_APPROVED_SSL_ROOT_CERT`.

Load a separately controlled, random key of at least 32 bytes as base64 in
`ISTARI_BACKUP_INTEGRITY_KEY_BASE64`. Keep it in the operational secret store,
separate from backup storage and the database credentials. For example, generate
the value inside the approved secret-management boundary, not in repository
configuration. Then run:

```powershell
pwsh -File scripts/backup-postgres.ps1 -OutputDirectory C:\istari-backups
```

Retain the `.dump` and matching `.sha256.json` together in controlled storage.
A file is not a valid backup merely because `pg_dump` exited successfully. The
script also validates the catalogue and records an HMAC-authenticated checksum,
filename and creation timestamp. Loss of the separate integrity key makes restore
verification impossible, so protect and recover it under the operational key
management procedure.

Backups are immutable copies and do not receive row-level deletion. Retain each
backup for the separately approved backup period, currently 35 days, then expire
the whole backup and manifest through the storage lifecycle. A legal hold pauses
expiry for the complete affected backup set. Restoring an older backup must run
retention before service is opened and must not reintroduce disposed data into
the live database. Record lifecycle expiry and restore-time disposal as
content-free operational evidence.

Audit HMAC rotation uses `AUDIT_HMAC_ACTIVE_KEY_ID` and a JSON
`AUDIT_HMAC_KEYRING`. Add the new key, retain every old key referenced by stored
events, change the active ID, verify request and administration chains, then
deploy. Never remove a verification key until every referencing event and backup
has lawfully expired. Losing an old key makes its historic chain unverifiable.

## Isolated restore rehearsal

Create a new empty PostgreSQL database with a dedicated restore owner. Set
`ISTARI_RESTORE_DATABASE_URL` for that database, applying the same remote TLS and
approved CA-path rule. Load the original backup integrity key from the separate
secret store, then run:

```powershell
pwsh -File scripts/restore-postgres.ps1 `
  -BackupFile C:\istari-backups\istari-YYYYMMDDTHHMMSSZ.dump `
  -EvidenceDirectory .local-evidence\restore `
  -Confirmation RESTORE_ISOLATED_DATABASE
```

The script authenticates the manifest and checksum before connecting. It refuses
a target containing any public table, then verifies archive structure, Alembic
revision, content-free counts and both audit chains.
Afterwards, reconcile restored active requests with Camunda before considering a
recovery usable.

## Operational snapshot

Run the content-free database snapshot with:

```powershell
uv run --directory apps/api istari-maintenance health-snapshot
```

For the local stack, `scripts/check-operational-health.ps1` also checks API
readiness and validated backup age. Follow alert handling and escalation in
`docs/operations/SUPPORT_AND_INCIDENT_RUNBOOK.md`.
