# Security review remediation matrix, 13 August 2026

This matrix is the completion record for
`docs/specs/security-review-remediation-2026-08-13.md`. A row may be marked
complete only when the implementation, focused regression and broader gate have
all passed against the current worktree.

| Finding | Required implementation evidence | Required verification | Status |
| --- | --- | --- | --- |
| Internal current-owner messages visible to Customers | Typed event visibility and actor-aware history projection | Customer exclusion and staff inclusion API tests | In progress |
| Stale contributor assignment | Final-boundary lock and eligibility check for every selected Analyst | Transfer, deactivation and role-change dispatch tests | In progress |
| Raw Uvicorn and Nginx access logs | Default access logs disabled and minimised route logger configured | Built-container path/query/user-agent canary | In progress |
| Passive polling extends idle sessions | Passive authentication path that does not touch activity plus browser privacy lock | Poll beyond idle deadline and focus/visibility tests | In progress |
| Password-assistance race and timing differential | Atomic budgets and identity-neutral response path | Multi-session concurrency and branch-equivalence tests | In progress |
| Login global-budget and account-lockout denial of service | Hierarchical budget consumption and non-abusable account protection | One-source saturation and named-account abuse tests | In progress |
| Abandoned upload storage exhaustion | Pre-storage quotas, bounded drafts/grants and orphan reaper | Expiry, finalisation-failure and quota tests | In progress |
| Office central-directory exhaustion | Pre-parser directory bounds and scan resource limit | Real adversarial ZIP and concurrency tests | In progress |
| Backup/restore TLS downgrade | Remote `verify-full` and trust-path enforcement | URL parser and operations contract tests | In progress |
| EOL vulnerable Node builder | Supported digest-pinned LTS builder and tool-image scanning | Exact-image Trivy and SBOM gates | In progress |
| Capacity reservation overlap race | Database non-overlap invariant | Two-transaction overlap test | In progress |
| WIP and dependency concurrency races | Aggregate/database serialisation | Concurrent WIP and cycle tests | In progress |
| Incomplete content retention | Lifecycle policy, legal hold and separately authorised disposal | Persistent-model inventory and disposal tests | In progress |
| Missing attributable security outcomes | Content-free independent security-event stream | Login, rate-limit, step-up, CSRF and denial tests | In progress |
| Audit-key rotation breaks history | Key IDs, verification keyring and continuity evidence | Pre/post-rotation chain verification | In progress |
| Password fields retained | Failure and mode-transition clearing | Login and step-up browser tests | In progress |
| Cross-tab stale protected content | Logout/expiry broadcast and local cache privacy lock | Two-tab, offline and absolute-expiry tests | In progress |
| Customer organisation enumeration | Server-side directory policy | Customer denial and staff access tests | In progress |
| Request activity misclassified as content-free | Assurance and lifecycle classification corrected | Documentation contract and canary inventory | In progress |
| Mutable Dockerfile frontend | Immutable or engine-bundled frontend selection | Repository Dockerfile policy test | In progress |
| Weak local orchestration segmentation | Networkless/read-only init and isolated orchestration network | Compose contract and local smoke test | In progress |
| `GET /auth/me` mutates CSRF state | Read-only session read or safe multi-token bootstrap | Parallel-tab token and no-write tests | In progress |

## Global release evidence

- [ ] Backend test suite passes with at least 95 per cent line and branch coverage.
- [ ] Frontend test suite passes with at least 95 per cent line and branch coverage.
- [ ] Repository quality gate, documentation, licences, type checking and lint pass.
- [ ] Bandit, Python audit and Node audit pass.
- [ ] Gitleaks and reachable-history TruffleHog gates pass.
- [ ] Runtime, builder and security-tool image vulnerability scans pass.
- [ ] Alembic upgrades and downgrades cleanly and metadata matches migration head.
- [ ] Local Compose health and workflow smoke checks pass.
- [ ] Independent code-quality and cyber-security reviews have no unresolved
  Critical, High or Medium finding in the remediated scope.
