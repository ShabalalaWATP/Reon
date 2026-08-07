# Migration and restore evidence

## Current implementation evidence

Recorded on 7 August 2026.

Migration `0011_operational_evidence` has passed an empty-database upgrade,
metadata drift check, upgrade from `0010`, downgrade to `0010`, re-upgrade to
head and a second drift check using the isolated SQLite compatibility harness.
The maintenance interface then passed a dry-run retention check, restore
verification and a deliberately unhealthy operational snapshot.

The PostgreSQL backup and restore controls are implemented in:

- `scripts/backup-postgres.ps1`;
- `scripts/restore-postgres.ps1`;
- `scripts/test-operations-scripts.ps1`;
- `apps/api/src/istari_api/restore_verification.py`.

The scripts require a custom-format archive, validate its catalogue, protect the
result with a SHA-256 manifest, refuse a non-empty restore target, verify the
checksum and run schema, row-count and audit-chain checks after restore. Static
PowerShell parsing and control-contract checks pass.

## PostgreSQL 17.9 rehearsal

Recorded on 7 August 2026 using two isolated, disposable containers and no
existing development data.

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
