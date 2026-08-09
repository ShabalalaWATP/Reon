# August 2026 security remediation

## Status and scope

Status: implementation approved on 9 August 2026.

This specification remediates the findings from the full repository, dependency,
container and local dynamic security assessment completed on 9 August 2026. It
applies to the synthetic local MVP and to the production fail-closed boundary.

Two controls are deliberately outside this change because the product owner
excluded them:

- the local synthetic username and shared-password authentication model, including
  replacement with OIDC or MFA;
- GitHub branch-protection settings.

The exclusion does not permit demo identities outside local or test environments.
Existing production validation must continue to reject them.

## Security outcomes

### Runtime supply chain

- PostgreSQL uses the patched 17.10 release and a minimal Alpine runtime.
- The PostgreSQL runtime does not contain or invoke the vulnerable `gosu` helper.
- API build tooling and the vulnerable base-image copy of `pip` are absent from the
  final runtime stage.
- Nginx runs as a fixed non-root identity on port 8080 with no Linux capabilities,
  a read-only root filesystem and writable temporary storage only under `/tmp`.
- Optional Camunda packages that the PostgreSQL topology cannot use are removed,
  including the SQL Server JDBC driver. Unused vulnerable archive and HTTP/2
  utilities are removed with their package inventory records.
- CI builds and scans API, web, PostgreSQL, Camunda and ClamAV images with a current
  vulnerability database. High or critical findings are not silently ignored.
- CI produces machine-readable SBOMs for every deployed image.
- uv, pnpm and Dependabot defer ordinary newly published versions for seven days.
  Exact bootstrap exceptions can cover only versions already locked, audited and
  scanned; they do not bypass security updates or authorise later versions.
- pnpm rejects transitive exotic sources and package trust downgrades, apart from
  one exact reviewed legacy transitive version in the current lock.

### Malware-signature freshness

- A separate non-root ClamAV updater receives the dedicated outbound mirror
  network and writable definition volume. It does not parse submitted files.
- API-to-clamd traffic remains confined to the internal scanner network. Clamd
  has no outbound network, mounts definitions read-only and runs non-root with no
  capabilities and a read-only root.
- Container health requires both a responsive daemon and a daily signature whose
  signed build timestamp is no older than the configured maximum age. Copy or
  restore time is not accepted as signature age.
- Signature update failure therefore makes dependent application startup fail
  closed instead of reporting a misleading healthy state.

### Login resource protection

- A PostgreSQL-backed fixed-window limiter durably consumes global and
  source-specific capacity in a separate short transaction before Argon2
  verification, so limits are shared by every API replica without holding its
  global row lock during hashing.
- Connection acquisition and the complete limiter transaction have an explicit
  deadline. PostgreSQL also applies transaction-local statement and row-lock
  deadlines. Contention fails account-neutrally before account lookup or hashing,
  and cancellation cleanup cannot remain unbounded.
- Source identifiers are one-way digests. Raw IP addresses and usernames are not
  stored in the limiter table or emitted in security logs.
- Forwarded addresses are trusted only when the direct peer belongs to an explicit
  configured proxy network. Invalid or ambiguous forwarded values fall back to the
  direct peer.
- A process-wide concurrency limiter bounds simultaneous Argon2 work in each API
  replica.
- Rate-limit responses remain account-neutral and include a bounded `Retry-After`
  value.
- Expired limiter records are pruned without an unbounded per-request table scan.

### Browser and management surface

- Production application construction disables OpenAPI, Swagger UI and ReDoc.
- Health routes are omitted from the schema and remain reachable only on the
  private API listener described by the deployment boundary.
- All API responses are non-cacheable and include same-origin opener, embedder and
  resource isolation headers in addition to the existing controls.
- The SPA index is explicitly revalidated, while immutable build assets may retain
  their normal cache behaviour.

### Security gates and operational readiness

- The deliberate historical URI test fixture has one exact, hashed, expiring
  TruffleHog exception. Verified findings can never be allow-listed.
- The current fixture no longer contains a literal credential-bearing URI.
- CodeQL URL validation uses exact canonical collection equality rather than a
  substring-style test expression.
- Any unavoidable Semgrep suppression is local to an immutable evidence statement
  and carries a reason.
- A fresh synthetic environment creates activation and independent approval
  evidence and returns ready only after the configured Camunda workflow is marked
  available and the independent worker is fresh.
- Existing invalid configuration data is not silently granted fabricated approval.
  Operators must activate it through the controlled lifecycle or reset a disposable
  synthetic environment.

## Acceptance criteria

1. Backend and frontend test suites retain at least 95 per cent line and branch
   coverage.
2. Two independent database sessions observe and enforce the same login budget;
   cancellation cannot discard an accepted attempt and slow hashing holds no
   limiter row lock.
3. A real PostgreSQL transaction holding the global limiter row causes login to
   return temporarily unavailable within the configured deadline. No account
   lookup or hash begins, and authentication recovers after the lock is released.
4. Unknown usernames are rejected before password hashing after the shared budget
   is exhausted.
5. Forged forwarding headers from untrusted peers do not create new source buckets.
6. Production FastAPI instances expose none of `/docs`, `/redoc` or
   `/openapi.json`.
7. The built API, web, PostgreSQL, Camunda and ClamAV images run their expected
   entry points and have no unaccepted high or critical Trivy finding.
8. The web container reports a non-zero UID and remains healthy with a read-only
   root filesystem.
9. Stale ClamAV definitions fail the container health check even after a current
   filesystem timestamp is applied; clamd has no external egress and only the
   separate updater can reach the configured signature mirror.
10. Gitleaks and the reachable-history TruffleHog gate report no unapproved finding.
11. Bandit, Ruff security rules, Semgrep, dependency audits, Compose validation and
    the repository quality gates pass.
12. Alembic reports no difference between current ORM metadata and a database at
    migration head, and the metadata-alignment migration downgrades and upgrades
    without changing business data.

## Non-goals

- This work does not claim that local Compose is a production architecture.
- It does not implement enterprise identity, production object storage, a managed
  CDR service, cloud WAF rules or GitHub repository governance.
- It does not rewrite Git history to remove a synthetic negative-test fixture.
