# Operations and recovery threat model

## Assets and trust boundaries

Assets are the PostgreSQL product store, Camunda workflow state, audit-chain keys,
backup files, source-controlled BPMN and operational evidence. Operator shells,
backup storage and restore targets are separate trust boundaries.

## Threats and controls

| Threat | Control | Verification |
| --- | --- | --- |
| Retention deletes active or accountable data | Fixed allow-list, age and state predicates, bounded batches, one transaction | Boundary and rollback tests |
| An operator runs deletion accidentally | Dry-run default plus exact `APPLY_RETENTION` confirmation | CLI and service tests |
| Retention report leaks content | Counts and policy metadata only | Schema tests and log inspection |
| Concurrent state change makes a candidate unsafe | Reapply eligibility predicates in the delete statement | Concurrency-oriented repository test |
| Backup is incomplete or corrupted | Custom format validation, SHA-256 manifest, non-zero command handling | Backup rehearsal |
| Restore overwrites live data | Exact confirmation and empty-target precondition; no `--clean` | Restore negative test |
| Restored product and Camunda state diverge | Post-restore reconciliation and controlled interruption scenarios | Recovery evidence |
| A restored active pointer references incomplete or unapproved configuration | Readiness verifies a complete bundle, approved evidence and activation with the exact canonical digest | Restore-integrity and tamper tests |
| Configuration components are altered after approval | PostgreSQL seals non-proposed snapshots and approved workflow identity; readiness recomputes approval evidence | Runtime-role denial and digest-tamper tests |
| A pre-sealing baseline is treated as approved during upgrade | Fail readiness closed and require a newly reviewed successor; never backdate evidence | Legacy-upgrade rehearsal and runbook review |
| Organisation closure and candidate choices disagree | Rebuild closure from the immutable current snapshot and verify exact parent relationships before routing resumes | Projection and forged-parent tests |
| In-flight pins reference an unavailable or mismatched snapshot | Validate the pinned configuration and workflow evidence at submission and fail new routing closed on mismatch | Pinning and readiness tests |
| A partial multi-store restore releases incorrect products | Reconcile PostgreSQL package metadata, private objects, scan evidence, Camunda state and projections before reopening | Multi-store recovery gate |
| Search materialisation lags configuration activation | Search only the authorised current response, display current context and treat search as degraded UI, never routing authority | Browser and stale-result tests |
| Broad recovery replays unrelated or valid commands | Exact request identifier, failed-state predicate, dry-run default, fixed confirmation and transactional state recheck | Recovery service and CLI tests |
| Dependency outage invents or duplicates a task | Transactional outbox, bounded delayed retries and task-key reconciliation; never project an unconfirmed task | Controlled Camunda and PostgreSQL interruption |
| API replica scaling multiplies maintenance work | Run maintenance as a separate workload and fence singleton jobs with expiring PostgreSQL leases | Overlapping worker and lease-takeover rehearsal |
| Worker stops while API health remains green | Persist a content-free heartbeat and make readiness fail when it becomes stale | Stale-heartbeat readiness test |
| Membership projection is stale at an effective boundary | Query only due transitions in the worker, retain the effective-dated timeline as authority and fail closed for unapplied future access | Due-transition and authorisation tests |
| Backup credentials or content leak | No credential logging, restrictive directory ACL, controlled storage and deletion | Script review and operator evidence |
| Audit evidence is altered | ORM guards where applicable, database-role restrictions and independent chain verification | Tamper and privilege tests |
| Docker ignore policy hides a force-added tracked credential file, or local generated state enters a scan image | Stage exactly `git ls-files`, rename ignore policies to inert scanned evidence names, and build only from that new directory; untracked local files never enter the context | Tracked environment-file regression plus fresh digest-pinned Gitleaks build and inventory evidence |
| A removed credential remains reachable in Git history | Digest-pinned history scan fails on every verified or unapproved unknown finding; an exact synthetic test-fixture fingerprint needs a reason and expiry | TruffleHog gate against the root commit and later reachable history, including exception expiry and stale-entry tests |
| BuildKit exports scan evidence without executing an independent policy stage | Make the final TruffleHog evidence stage copy from the gate stage, not directly from the scanner; test that dependency and build the evidence target in CI | Dockerfile dependency regression test plus a digest-pinned evidence build |
| A vulnerable deployed service is omitted from scanning | Build API, web, PostgreSQL, Camunda and ClamAV images, fail each on high or critical findings and retain an SBOM for each image | CI all-image Trivy gates and CycloneDX artefacts |
| A base, CI-tool or runtime dependency vulnerability remains unnoticed, or a malicious new release is consumed before review | Lock dependencies, apply seven-day uv, pnpm and Dependabot version cooldowns, use a Dependabot-supported pnpm major, block exotic transitive Node sources and trust downgrades, schedule native uv, npm, Actions, Docker and Compose checks for every manifest, exclude only locally built Compose output tags already covered by Dockerfile updates, audit all runtime/development/test locks, and rerun current-database audits during release. Bootstrap exceptions are exact-version only | Frozen-install policy verification, Dependabot configuration contract, all-group pip-audit, full pnpm audit and image scans |
| ClamAV updates on disk but serves an older loaded database, or copied stale definitions appear new | Derive age from signed database build metadata and require clamd responsiveness plus loaded/on-disk version equality | Current-mtime stale-copy rejection and health test after a real update and reload |
| A compromised untrusted-content scanner becomes an outbound pivot | Run clamd non-root with no capabilities, a read-only root and signature mount, and only an internal network; isolate writable definitions and mirror egress in a separate non-scanning updater | Compose topology contract, container inspection and clamd egress-denial probe |
| A cloud sandbox exposes the local Camunda or application topology | Keep all Compose ports on VM loopback; use SSM, IAP/SSH or Bastion/SSH forwarding; prohibit real data | Configuration validation, platform-guide review and network inspection |
| A setup guide creates a tunnel to a port that is not reachable by design | Tunnel SSH/management first, then forward to VM loopback; test the documented path | Documentation link/contract review and sandbox rehearsal |
| Production database traffic is encrypted without server identity verification | Require asyncpg-compatible `ssl=verify-full` and an approved CA/hostname | Settings rejection and SQLAlchemy dialect connect-argument test |
| Disabling the configuration administration screen bypasses runtime integrity readiness | Always verify the active sealed configuration and approved workflow independently of the UI feature flag | Readiness tests with administration disabled and tampered workflow evidence |
| A very broad tracking scope exhausts query parameters or progressively slows offset pages | Load immutable policies in bounded batches, use scope-first composite indexes and keyset pagination | Fixed first/deep statement counts and PostgreSQL target-scale plans |

## Residual risks

The local pilot scripts cannot supply enterprise backup encryption, immutable
storage, point-in-time recovery, key escrow, production alert delivery or an
accepted multi-store consistency point. RTO, RPO, invocation authority and
manual fallback are not yet approved. Those controls require the selected
hosting platform and operational owner before production.

Private AWS, Google Cloud and Azure VM procedures remain synthetic evaluation
patterns. The local Camunda API is unauthenticated, product files use a local
volume, application OIDC is absent and the web image is local-host specific.
These limitations are production blockers, not configuration tasks.
