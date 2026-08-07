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
| Broad recovery replays unrelated or valid commands | Exact request identifier, failed-state predicate, dry-run default, fixed confirmation and transactional state recheck | Recovery service and CLI tests |
| Dependency outage invents or duplicates a task | Transactional outbox, bounded delayed retries and task-key reconciliation; never project an unconfirmed task | Controlled Camunda and PostgreSQL interruption |
| Backup credentials or content leak | No credential logging, restrictive directory ACL, controlled storage and deletion | Script review and operator evidence |
| Audit evidence is altered | ORM guards where applicable, database-role restrictions and independent chain verification | Tamper and privilege tests |
| A shared Docker ignore policy hides source from secret scanning or includes generated browser state | Dedicated secret-scan ignore policy includes documentation and tests while excluding credentials, caches, generated evidence and browser profiles | Fresh digest-pinned Gitleaks build and source-inventory review |
| A removed credential remains reachable in Git history | Digest-pinned history scan checks verified and unknown findings and fails on any result | TruffleHog gate against the root commit and later reachable history |

## Residual risks

The local pilot scripts cannot supply enterprise backup encryption, immutable
storage, key escrow or production alert delivery. Those controls require the
selected hosting platform and operational owner before production.
