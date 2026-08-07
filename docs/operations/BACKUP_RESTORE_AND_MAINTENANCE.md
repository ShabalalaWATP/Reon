# Backup, restore and maintenance

## Database identities

Local Compose uses four separate PostgreSQL service identities:

- `APP_DATABASE_USER` owns the application schema and is available only to the
  one-shot migrator;
- `APP_RUNTIME_DATABASE_USER` runs the API with ordinary data access but cannot
  alter the schema or mutate append-only evidence;
- `APP_BACKUP_DATABASE_USER` has read-only access for `pg_dump`;
- `CAMUNDA_DATABASE_USER` is confined to the separate Camunda database.

All passwords must differ from one another, the bootstrap password and the demo
login password. Do not place connection strings in command history or evidence.

## Retention

Preview eligible counts without changing data:

```powershell
uv run --directory apps/api istari-maintenance retention
```

Apply the approved policy only after reviewing the dry run:

```powershell
uv run --directory apps/api istari-maintenance retention --confirmation APPLY_RETENTION
```

The command deletes at most 1,000 eligible rows per class and emits counts only.

## Backup

Set `ISTARI_BACKUP_DATABASE_URL` for the read-only backup identity, then run:

```powershell
pwsh -File scripts/backup-postgres.ps1 -OutputDirectory C:\istari-backups
```

Retain the `.dump` and matching `.sha256.json` together in controlled storage.
A file is not a valid backup merely because `pg_dump` exited successfully. The
script also validates the catalogue and records its checksum.

## Isolated restore rehearsal

Create a new empty PostgreSQL database with a dedicated restore owner. Set
`ISTARI_RESTORE_DATABASE_URL` for that database and run:

```powershell
pwsh -File scripts/restore-postgres.ps1 `
  -BackupFile C:\istari-backups\istari-YYYYMMDDTHHMMSSZ.dump `
  -EvidenceDirectory .local-evidence\restore `
  -Confirmation RESTORE_ISOLATED_DATABASE
```

The script refuses a target containing any public table. It verifies checksum,
archive structure, Alembic revision, content-free counts and both audit chains.
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
