# Security matrix evidence

## Result

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

## Principal automated evidence

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

Technical evidence is ready. Formal security-owner acceptance and a scan of the
first reviewed Git baseline remain separate gates.
