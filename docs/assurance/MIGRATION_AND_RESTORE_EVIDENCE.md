# Migration and restore evidence

## Current implementation evidence

Current-head record reviewed on 14 August 2026.

The current migration head is `0047_action_view_contexts`. The application,
restore script and restore verifier use that same default rather than a stale
embedded revision. Empty-database upgrade, metadata drift and downgrade/re-upgrade
checks run through the isolated compatibility harness as release gates. The
maintenance interface also covers dry-run retention, restore verification and a
deliberately unhealthy operational snapshot.

Revision 0019 adds durable worker state, due-membership projection markers,
fenced product-operation leases and the composite feed indexes used by keyset
pagination. Revision 0020 adds shared login-attempt windows. Revision 0021 gives
long check constraints stable readable names and represents migration-owned
performance indexes in ORM metadata. Revision 0022 replaces internal routing
questions on Customer requests with the richer Customer-owned requirement set
and adds reviewed account-request records. It preserves sealed configuration
snapshots rather than rewriting their historical field lists.
Revision 0028 adds normalised unique account email, the versioned global visual
classification singleton and privacy-minimised password-assistance attempt
records. Revision 0029 installs PostgreSQL `pg_trgm` and pgvector, adds the
all-field request-search projection, backfills every submitted request and
creates GIN, trigram and HNSW indexes. It also extends recorded related-request
decisions with `NOT_RELEVANT`. `scripts/restore-postgres.ps1` and the maintenance
verifier default to the exact `0047_action_view_contexts` revision. Revision
0030 adds bounded self-declared user skills, revision 0031 repairs role-aware
action audiences and queue links, and revision 0032 applies the current
plain-language coordination presentation values.

The repository now contains an executable PostgreSQL gate for revisions 0043 to
0047. It uses two uniquely named disposable databases: one populated at 0043 for
stepwise upgrade, downgrade and re-upgrade, and one empty database for the forward
path. It asserts real backfills, unique and check constraints, the conversation
delivery trigger, QC membership projection, documented downgrade losses and
`alembic check`. The explicit PostgreSQL CI lane treats any skip as a failure.

On 14 August 2026 the harness passed against disposable PostgreSQL databases
through the WSL Docker integration. A populated database upgraded stepwise from
0043 to 0047, downgraded to 0043 and re-upgraded to 0047. A separate empty
database upgraded to head. Both paths passed `alembic check` with no metadata
drift. The rehearsal also verified real backfills, constraints, indexes,
conversation delivery triggers, QC membership projection and documented
downgrade losses. Defects in the 0046 downgrade constraint name, action-view
unique-constraint metadata and the 0044 conversation visibility index were found
by this run and repaired before the successful result.

The PostgreSQL backup and restore controls are implemented in:

- `scripts/backup-postgres.ps1`;
- `scripts/restore-postgres.ps1`;
- `scripts/test-operations-scripts.ps1`;
- `scripts/lib/PostgresServiceFile.ps1`;
- `apps/api/src/mist_service/restore_verification.py`.

The scripts require a custom-format archive, validate its catalogue, protect the
result with a SHA-256 manifest, refuse a non-empty restore target, verify the
checksum and run schema, row-count and audit-chain checks after restore. Database
credentials are passed to PostgreSQL tools through a permission-restricted,
temporary libpq service file, not a password-bearing child-process argument.
Static PowerShell parsing and control-contract checks pass.

## PostgreSQL migration and guard evidence for revision 0029

On 10 August 2026 the retained synthetic PostgreSQL 17.10 database was upgraded
to `0029_related_request_search` through the new locally built PostgreSQL image.
The database reported `pg_trgm` 1.6 and vector 0.8.1, all ten existing submitted
requests were backfilled, and the independent worker moved every projection to
`READY`. Inspection confirmed the weighted full-text GIN, narrative trigram GIN
and cosine HNSW indexes. The runtime role retained ordinary table DML and the
backup role retained read-only access. A forward migration and live hybrid API
query passed.

The current API image then upgraded a separate PostgreSQL 17.10 database created
from `template0` through every revision to 0029, downgraded to 0028, re-upgraded
and passed `alembic check` without drift. The exact disposable database was
removed after the successful rehearsal. This also proves the migration with the
real vector and trigram extensions, while the retained database proves the
ten-record data backfill.

The retained local development volume was originally initialised on glibc and
therefore still records glibc collation version 2.36. Its collation-dependent
indexes were rebuilt after the Alpine switch, but musl exposes no replacement
version and PostgreSQL correctly refuses `REFRESH COLLATION VERSION`. A logical
dump and restore into a fresh Alpine-created volume remains required before that
retained local volume can be treated as release-candidate restore evidence. The
fresh PostgreSQL component and disposable migration databases do not inherit
this development-only warning. No direct system-catalog edit was used.

The following revision 0028 rehearsal is retained as historical evidence.

On 10 August 2026 a separate disposable PostgreSQL 17 database created from
`template0` was upgraded from empty through every revision to
`0028_access_classification`, downgraded to `0027_workspace_collaboration`,
re-upgraded and checked with `alembic check`. The final revision was exactly the
single head and no model drift was detected. The first rehearsal exposed a
text-typed singleton UUID bind that SQLite had accepted; the migration was fixed
to use an explicit UUID bind and the entire clean sequence then passed. The
temporary database was removed after verification. The subsequent live
classification update exposed a second SQLite-masked boundary: SQLAlchemy was
persisting the Python enum member name `OFFICIAL_SENSITIVE` while the migration
constraint correctly accepts the public value `OFFICIAL-SENSITIVE`. Enum
persistence now uses declared string values, a metadata regression test protects
the mapping, and the PostgreSQL update succeeded before the singleton was
restored to `OFFICIAL`.

On 10 August 2026 a disposable PostgreSQL 17 database created from `template0`
was upgraded from an empty application schema through every revision to
`0027_workspace_collaboration`. It then downgraded through the four unified
workspace revisions to `0023_cancellation_profiles`, re-upgraded to head and
passed `alembic check` with no new upgrade operations. The temporary database
was removed after the successful rehearsal. This proves clean installation and
reversibility of the new membership, participant, calendar-link and
collaboration schema. It does not replace the multi-store backup and restore
exercise required for a connected production release.

On 9 August 2026 the retained synthetic local PostgreSQL 17.10 database migrated
from `0011_operational_evidence` through `0027_workspace_collaboration`. The first
pre-release rehearsal correctly rejected an attempted update to a sealed
configuration snapshot, rolled the transaction back and exposed that the data
rewrite was unnecessary. Revision 0022 was corrected to leave sealed history
unchanged, then upgraded successfully. The rebuilt API image reported the new
head and `alembic check` reported no new upgrade operations. The same revision
also passed the isolated SQLite empty upgrade, drift, downgrade and re-upgrade
compatibility checks. The retained local database's imported baseline workflow
is not operationally attested, so this check does not claim full application
readiness or replace a fresh current-head PostgreSQL downgrade/re-upgrade and
backup/restore rehearsal.

Earlier on 9 August 2026 the fresh synthetic QA PostgreSQL 17.10 database migrated from
no application schema to `0021_schema_metadata`. The current API image reported
that exact head and `alembic check` reported no new upgrade operations. With the
application stopped, revision 0021 downgraded to `0020_login_rate_limits` and
upgraded to head again. A second metadata check remained clean, and application
readiness returned `ok` for database, workflow, configuration and maintenance.
The migration only renames check constraints; it does not rewrite business rows.

The 8 August 2026 load rehearsal used a clean disposable PostgreSQL 17.9
database migrated from no schema to `0019_runtime_scaling`. Application startup
seeded the documented identities and the sealed baseline. The deterministic
rehearsal then created 250
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
| Runtime privilege | Synthetic users seeded; schema creation and audit-table update were denied |
| Backup privilege | Read-only identity could create the archive but could not update application data |
| Archive | Custom-format catalogue validation and SHA-256 calculation passed; rehearsal copy was removed afterwards |
| Restore precondition | Target public schema contained zero tables before restore |
| Clean restore | `--no-owner`, `--no-acl`, single-transaction restore passed |
| Integrity | Revision, user count, pending-command count and request and administrator audit chains passed |
| Recovery target | Restore plus integrity verification completed in 1.22 seconds, below the 30-minute target |
| Cleanup | Both exact rehearsal containers, volumes and the temporary archive were removed |

The rehearsal used the same PostgreSQL native operations and verification command
as the operator scripts. It is pilot evidence, not proof of enterprise backup
storage, encryption, key escrow or a hosted disaster-recovery service.

The complete PostgreSQL extension and data-backfill rehearsal is recorded
through revision 0029. The current codebase also exercises revisions 0030 to
0032 through migration and application tests, but a fresh end-to-end PostgreSQL
clean install, downgrade and re-upgrade at revision 0032 remains required for
release acceptance. A current-candidate backup/restore run covering PostgreSQL,
product storage and workflow state together also remains open.
