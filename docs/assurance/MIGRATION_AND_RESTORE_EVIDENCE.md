# Migration and restore evidence

## Current implementation evidence

Recorded on 7 August 2026.

The current migration head is `0017_legacy_workflow_identity`. The application,
restore script and restore verifier use that same default rather than a stale
embedded revision. Empty-database upgrade, metadata drift and downgrade/re-upgrade
checks run through the isolated compatibility harness as release gates. The
maintenance interface also covers dry-run retention, restore verification and a
deliberately unhealthy operational snapshot.

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
