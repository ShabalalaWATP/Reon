# Migration and restore evidence

## Current implementation evidence

Current-head record reviewed on 9 August 2026.

The current migration head is `0021_schema_metadata`. The application,
restore script and restore verifier use that same default rather than a stale
embedded revision. Empty-database upgrade, metadata drift and downgrade/re-upgrade
checks run through the isolated compatibility harness as release gates. The
maintenance interface also covers dry-run retention, restore verification and a
deliberately unhealthy operational snapshot.

Revision 0019 adds durable worker state, due-membership projection markers,
fenced product-operation leases and the composite feed indexes used by keyset
pagination. Revision 0020 adds shared login-attempt windows. Revision 0021 gives
long check constraints stable readable names and represents migration-owned
performance indexes in ORM metadata. `scripts/restore-postgres.ps1` and the
maintenance verifier now default to the exact `0021_schema_metadata` revision.

The PostgreSQL backup and restore controls are implemented in:

- `scripts/backup-postgres.ps1`;
- `scripts/restore-postgres.ps1`;
- `scripts/test-operations-scripts.ps1`;
- `scripts/lib/PostgresServiceFile.ps1`;
- `apps/api/src/istari_service/restore_verification.py`.

The scripts require a custom-format archive, validate its catalogue, protect the
result with a SHA-256 manifest, refuse a non-empty restore target, verify the
checksum and run schema, row-count and audit-chain checks after restore. Database
credentials are passed to PostgreSQL tools through a permission-restricted,
temporary libpq service file, not a password-bearing child-process argument.
Static PowerShell parsing and control-contract checks pass.

## Current-head PostgreSQL migration and guard evidence

On 9 August 2026 the fresh synthetic QA PostgreSQL 17.10 database migrated from
no application schema to `0021_schema_metadata`. The current API image reported
that exact head and `alembic check` reported no new upgrade operations. With the
application stopped, revision 0021 downgraded to `0020_login_rate_limits` and
upgraded to head again. A second metadata check remained clean, and application
readiness returned `ok` for database, workflow, configuration and maintenance.
The migration only renames check constraints; it does not rewrite business rows.

Earlier on 8 August 2026 a clean disposable PostgreSQL 17.9 database migrated from no
schema to `0019_runtime_scaling`. Application startup seeded all 73 documented
identities and the sealed baseline. A deterministic rehearsal then created 250
active users, 2,500 request, draft, work, route/history and Board records, plus
5,000 calendar records. All expected indexes were present; target-scale
statement counts, query plans and two-worker contention passed. The exact
database, API and web containers and their network were removed after evidence
capture. Content-free results and hashes are recorded in
`output/load/runtime-scale-manifest.json`.

On 7 August 2026 an isolated PostgreSQL 17 database was upgraded from empty to
`0018_configuration_sealing`. First startup created the synthetic baseline
through the proposed-change, validation, independent-approval and activation
states required by the database guards. Approval and activation digests were
non-zero and equal. The runtime role was denied when it attempted to move a
sealed component into another configuration or alter an approved workflow's
core identity. An allowed operational availability update remained possible.
The disposable database was removed after verification. The interactive command
transcript and database artefact were not retained, so this is supporting local
evidence, not a reproducible release artefact. Current-head acceptance still
requires an immutable command log, environment inventory, checksums and retained
sanitised results tied to the candidate commit.

On 8 August 2026 the current working tree was independently exercised again in
a second disposable PostgreSQL 17 database. Empty-to-head migration and startup
created 73 synthetic users, one approval and one activation with matching
non-zero digests. Direct inserts using an invalid approval actor/event order and
an invalid activation actor were both rejected by the new PostgreSQL guards.
The database and temporary application container were removed afterwards. This
follow-up is recorded terminal evidence only and does not close the immutable
release-artefact requirement above.

An existing local QA database was also downgraded from 0018 to 0017 and upgraded
again. Its historical imported baseline pre-dated independent approval evidence,
so readiness correctly failed closed. The supported upgrade action is to create,
validate, independently approve and activate a successor. Operators must not
manufacture or backdate historical approval evidence.

## Historical PostgreSQL 17.9 rehearsal

Recorded on 7 August 2026 using two isolated, disposable containers and no
existing development data. This rehearsal covered head `0011_operational_evidence`;
it remains historical evidence and does not replace a rehearsal at the current
head before pilot acceptance.

| Check | Result |
| --- | --- |
| Empty migration | Upgrade from no schema to `0011_operational_evidence` passed |
| Drift | `alembic check` reported no new upgrade operations |
| Previous revision | Downgrade to `0010_admin_step_up`, re-upgrade and second drift check passed with seeded data |
| Runtime privilege | 72 synthetic users seeded; schema creation and audit-table update were denied |
| Backup privilege | Read-only identity could create the archive but could not update application data |
| Archive | Custom-format catalogue validation and SHA-256 calculation passed; rehearsal copy was removed afterwards |
| Restore precondition | Target public schema contained zero tables before restore |
| Clean restore | `--no-owner`, `--no-acl`, single-transaction restore passed |
| Integrity | Revision, 72-user count, pending-command count and request and administrator audit chains passed |
| Recovery target | Restore plus integrity verification completed in 1.22 seconds, below the 30-minute target |
| Cleanup | Both exact rehearsal containers, volumes and the temporary archive were removed |

The rehearsal used the same PostgreSQL native operations and verification command
as the operator scripts. It is pilot evidence, not proof of enterprise backup
storage, encryption, key escrow or a hosted disaster-recovery service.

The fresh 0021 migration and metadata rehearsal is not a complete current-head
backup and restore rehearsal. A current-head, multi-store rehearsal remains an
open Product Evolution recovery gate.
