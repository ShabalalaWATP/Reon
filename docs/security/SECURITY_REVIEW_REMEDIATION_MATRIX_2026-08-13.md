# Security review remediation matrix, 13 August 2026

This matrix is the completion record for
`docs/specs/security-review-remediation-2026-08-13.md`. A row may be marked
complete only when the implementation, focused regression and broader gate have
all passed against the current worktree.

| Finding | Required implementation evidence | Required verification | Status |
| --- | --- | --- | --- |
| Internal current-owner messages visible to Customers | Typed event visibility and actor-aware history projection | Customer exclusion and staff inclusion API tests | Complete |
| Stale contributor assignment | Final-boundary lock and eligibility check for every selected Analyst | Transfer, deactivation and role-change dispatch tests | Complete |
| Raw Uvicorn and Nginx access logs | Default access logs disabled and minimised route logger configured | Built-container path/query/user-agent canary | Complete |
| Passive polling extends idle sessions | Passive authentication path that does not touch activity plus browser privacy lock | Poll beyond idle deadline and focus/visibility tests | Complete |
| Password-assistance race and timing differential | Atomic budgets and identity-neutral response path | Multi-session concurrency and branch-equivalence tests | Complete |
| Login global-budget and account-lockout denial of service | Hierarchical budget consumption and non-abusable account protection | One-source saturation and named-account abuse tests | Complete |
| Abandoned upload storage exhaustion | Pre-storage quotas, bounded drafts/grants and orphan reaper | Expiry, finalisation-failure and quota tests | Complete |
| Office central-directory exhaustion | Pre-parser directory bounds and scan resource limit | Real adversarial ZIP and concurrency tests | Complete |
| Backup/restore TLS downgrade | Remote `verify-full` and trust-path enforcement | URL parser and operations contract tests | Complete |
| EOL vulnerable Node builder | Supported digest-pinned LTS builder and tool-image scanning | Exact-image Trivy and SBOM gates | Complete |
| Capacity reservation overlap race | Database non-overlap invariant | Two-transaction overlap test | Complete |
| WIP and dependency concurrency races | Aggregate/database serialisation | Concurrent WIP and cycle tests | Complete |
| Incomplete content retention | Lifecycle policy, legal hold and separately authorised disposal | Persistent-model inventory and disposal tests | Complete |
| Missing attributable security outcomes | Content-free independent security-event stream | Login, rate-limit, step-up, CSRF and denial tests | Complete |
| Audit-key rotation breaks history | Key IDs, verification keyring and continuity evidence | Pre/post-rotation chain verification | Complete |
| Password fields retained | Failure and mode-transition clearing | Login and step-up browser tests | Complete |
| Cross-tab stale protected content | Logout/expiry broadcast and local cache privacy lock | Two-tab, offline and absolute-expiry tests | Complete |
| Customer organisation enumeration | Server-side directory policy | Customer denial and staff access tests | Complete |
| Request activity misclassified as content-free | Assurance and lifecycle classification corrected | Documentation contract and canary inventory | Complete |
| Mutable Dockerfile frontend | Immutable or engine-bundled frontend selection | Repository Dockerfile policy test | Complete |
| Weak local orchestration segmentation | Networkless/read-only init and isolated orchestration network | Compose contract and local smoke test | Complete |
| `GET /auth/me` mutates CSRF state | Read-only session read or safe multi-token bootstrap | Parallel-tab token and no-write tests | Complete |

## Global release evidence

- [x] Backend test suite passes with at least 95 per cent line and branch coverage.
- [x] Frontend test suite passes with at least 95 per cent line and branch coverage.
- [x] Repository quality gate, documentation, licences, type checking and lint pass.
- [x] Bandit, Python audit and Node audit pass.
- [x] Gitleaks and reachable-history TruffleHog gates pass.
- [x] Runtime, builder and security-tool image vulnerability scans pass.
- [x] Alembic upgrades and downgrades cleanly and metadata matches migration head.
- [x] Local Compose health and application workflow journeys pass.
- [x] Independent code-quality and cyber-security reviews have no unresolved
  Critical, High or Medium finding in the remediated scope.
