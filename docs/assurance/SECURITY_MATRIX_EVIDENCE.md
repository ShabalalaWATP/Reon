# Security matrix evidence

## Current supplementary result, 18 August 2026

The 17 August Codex Security remediation and the 18 August maintainability
candidate extend the dated baseline below. The complete current backend suite
passed 1,410 tests with 13 environment-specific skips at 98.83 per cent line and
95.10 per cent branch coverage. The complete frontend suite passed 582 tests at
98.80 per cent line and 95.07 per cent branch coverage. The independent
read-only application security review is scoped and identified in the
[security scan evidence](SECURITY_SCAN_EVIDENCE.md#current-maintainability-candidate-18-august-2026).
Its uncommitted review target means it is not immutable release evidence.

| Abuse scenario | Current enforced result and principal evidence |
| --- | --- |
| Workspace projection exposes fields outside the actor's action | Repository projections apply action-specific grant and object policy; unauthorised overview fields are omitted or explicitly marked unavailable before response construction. Covered by `test_team_workspace_projection_security.py` and workspace edge tests |
| Direct identifier or broad workspace read becomes object access | Exact team, request, membership, grant and permitted-action checks are repeated at the service and repository boundary; inaccessible objects retain the non-disclosing result |
| Pre-step-up bearer inherits privileged access | Successful step-up rotates bearer and CSRF hashes together; the earlier bearer fails and cross-tab reconciliation cannot restore superseded credentials. Covered by elevation repository, step-up service and browser rotation-race tests |
| Encoded Office or PDF active behaviour reaches product review | Bounded semantic Office inspection and lexical PDF action inspection fail closed before a clean result; superficial byte matching is not treated as sufficient |
| Scan admission queues unbounded upload spools | The composite scan permit is acquired before source iteration and first spool; object, decoded-content, parser and concurrency bounds apply before promotion |
| Notification projection failure is counted as worker success | Individual failure state and bounded backoff commit independently; the bounded batch continues and then reports an aggregate job failure to durable worker accounting |
| Analytics repair changes meaning or scans an unbounded source | Versioned definition metadata must match exactly; rebuild and replay require bounded source counts, and replay requires an explicit aware time interval |

The [Codex Security remediation matrix](../security/CODEX_SECURITY_REMEDIATION_MATRIX_2026-08-17.md)
records the dated findings and the production controls that remain open. Current
source verification does not replace hosted CodeQL, current-image scanning,
target-environment DAST, independent penetration testing or named security-owner
acceptance.

## Historical baseline, 7 August 2026

Recorded on 7 August 2026. The server-side permission and recovery matrix passed
in the 549-test backend suite, live PostgreSQL/Camunda journeys and restore and
interruption rehearsals. The policies are rechecked in application services and
locked repository transactions. React navigation is not an authority boundary.

| Abuse scenario | Enforced result and evidence |
| --- | --- |
| Cross-role action | Denied by action policy; API security and alternate-workflow tests |
| Cross-scope list or detail | Absent or denied without narrative leakage; request, tracking, statistics, calendar, roster and board scope tests |
| Direct identifier manipulation | Denied by object and organisation scope tests |
| Skipped, stale or repeated workflow step | Denied by expected task, state, assignee, action and version tests |
| Customer accesses another request or product | Denied in request and dissemination API security tests |
| Analyst approves or disseminates own output | Denied by separation-of-duties workflow tests |
| Non-child or skipped route | Denied by data-driven parent-child validation tests |
| Unstaffed destination | Creates an explicit waiting state; no SSG fallback |
| Tracker opens sibling-route or unreleased product data | Exact route membership is applied to list and direct detail; the read-only schema excludes actions, clarification, feedback and product data; product endpoints independently deny access |
| Platform Administrator opens request content | Denied; administration and request permissions are separate |
| Missing or reused CSRF | Denied by authentication and request-security tests |
| Expired, disabled or replayed session | Denied and session invalidated where required |
| Duplicate submit or command | Idempotency and outbox tests retain one request and one task |
| Audit record altered | Independent chain verification reports failure |
| Sensitive content sent to logs | Structured telemetry tests allow identifiers, timings and counts only |
| Dependency unavailable | Pending or controlled error state; no invented transition |
| Backup restored | Schema, counts and both audit chains verified in a clean PostgreSQL target |

## Principal baseline automated evidence

- `apps/api/tests/test_api_security.py`
- `apps/api/tests/test_auth_security.py`
- `apps/api/tests/test_request_scope_branches.py`
- `apps/api/tests/test_routing_validation_branches.py`
- `apps/api/tests/test_api_statistics.py`
- `apps/api/tests/test_api_calendar.py`
- `apps/api/tests/test_api_team_workspaces.py`
- `apps/api/tests/test_postgres_permissions.py`
- `apps/api/tests/test_workflow_camunda_recovery.py`
- `apps/api/tests/test_workflow_recovery.py`
- `apps/api/tests/test_audit_integrity.py`
- `apps/api/tests/test_telemetry.py`
- `apps/api/tests/test_restore_verification.py`

That baseline made its technical evidence ready. The current acceptance and
external-assurance gates remain open in the Definition of Done matrix.
