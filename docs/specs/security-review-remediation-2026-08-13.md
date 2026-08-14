# Security review remediation, 13 August 2026

## Status and scope

Status: implementation approved on 13 August 2026.

This specification covers every confirmed finding from the full application,
browser, workflow, data, dependency, container and operations security review.
Remediation must preserve the current Customer, routing, analysis, QC and product
delivery workflows. A passing test suite alone is not sufficient: each invariant
below requires a focused regression or adversarial test.

## Required security invariants

### Authentication and browser sessions

- Passive polling does not count as human activity and cannot extend the idle
  session deadline.
- The browser privacy-locks at idle and absolute expiry, clears protected caches,
  and propagates logout or expiry to every open tab.
- Login and step-up passwords are cleared after every completed attempt and when
  the user changes authentication mode.
- Password-assistance source and global budgets are consumed atomically before
  identity-dependent work. Public responses and response timing remain
  account-neutral.
- A source already blocked by its local login budget cannot exhaust shared global
  login capacity. Brute-force controls must not permit repeated hard lockout of a
  named account by an anonymous caller.
- Session bootstrap is safe across tabs. A read-only `GET` does not rotate the
  only valid CSRF token or otherwise mutate authentication state.

### Request and workflow confidentiality

- Customer-visible request history contains Customer-addressed and public
  lifecycle events only. Internal current-owner coordination remains available
  to authorised staff and is never inferred from a JSON convention alone.
- At workflow dispatch and final persistence, the lead and every contributor are
  active Analysts in the exact current delivery team. A stale participant gains
  no request, action or notification metadata.
- Customers cannot enumerate the global organisational or staffing topology.
  Submission continues to expose only the routing choices required for that
  Customer operation.

### Product content and uploads

- Aggregate package bytes are enforced before storage accepts another object.
  Active drafts, objects and bytes are bounded per request and actor, with an
  explicit global safety bound.
- Expired intents, abandoned quarantine objects and post-write database failures
  are reclaimed by an idempotent reconciliation process.
- Upload grants are bounded and expire from memory or durable storage.
- Office archives are rejected from bounded metadata before the ZIP parser can
  materialise an excessive central directory. Parsing and scanning have explicit
  concurrency, memory or process boundaries.

### Operations and supply chain

- Web and API operational logs never contain raw request targets, query values,
  credentials, arbitrary user agents or unapproved client identifiers. Runtime
  logging uses the validated correlation ID and route template.
- Remote backup and restore connections require hostname-verified PostgreSQL TLS
  and an approved trust path. Any plaintext exception is exact and loopback-only.
- Build and security-tool stages use a supported digest-pinned Node LTS release.
  CI scans and produces inventory for build/tool images as well as final runtime
  images.
- Dockerfile frontend resolution is immutable, or deliberately uses the locally
  bundled frontend without a mutable remote syntax tag.
- Local orchestration initialisation is read-only and networkless where possible,
  and the browser-serving container has no direct orchestration network path.

### Work-package concurrency

- The database prevents overlapping active capacity reservations for the same
  person, including concurrent requests for different work packages.
- WIP limits and dependency acyclicity remain true under concurrent transactions,
  not merely under sequential service checks.
- Constraint conflicts return deterministic, non-disclosing conflict responses.

### Evidence, audit and retention

- Request audit events are content-bearing records because messages and structured
  details can reproduce workflow content. They are not classified as safe,
  content-free operational telemetry.
- Audit events and anchors store versioned key IDs. Rotation retains old keys so
  pre-rotation request and administration chains remain verifiable.
- New request-event hashes bind the enforced audience and a hash-format version;
  legacy rows retain their original version so historical chains remain verifiable.
- Login, rate-limit, step-up, CSRF and authorisation outcomes create attributable,
  content-free security events in an independent transaction. Rejected privileged
  mutations cannot roll back their own denial evidence.
- Legal holds suspend disposal by target. Applying or releasing a hold and running
  disposal require distinct, attributable maintenance authorities outside ordinary
  application and Platform Administrator permissions.
- The retention schedule covers identities and account requests, completed requests
  and activity, feedback, clarifications, notifications, products and access events.
  External objects and their metadata are disposed as one operation or fail closed.

- Content-bearing records have an approved lifecycle covering identities,
  account requests, requests and activity, feedback, clarifications,
  notifications, products and product-access evidence.
- Legal holds prevent disposal. Disposal uses a separately authorised operational
  identity and produces content-free evidence of what policy was applied.
- Authentication outcomes, rate limits, privilege elevation and denial events are
  attributable using safe actor or one-way source identifiers without recording
  passwords, tokens, usernames or narrative.
- Audit events carry an audit-key identifier. Rotation retains a verification
  keyring and a continuity record so events written before and after rotation can
  be verified.
- Assurance documents classify request activity as content-bearing domain data.

## Acceptance evidence

1. Focused tests reproduce each original exploit or failure mode and pass only
   after the new invariant is enforced.
2. Real PostgreSQL concurrency tests cover password assistance, analyst assignment,
   capacity overlap, WIP limits and dependency cycles.
3. A built-container canary placed in path, query and user-agent inputs appears in
   neither web nor API logs; the minimised route-template event is present.
4. Adversarial Office ZIP fixtures are rejected within fixed time and memory
   budgets before `ZipFile` allocation.
5. Expired and orphaned upload objects are removed without deleting referenced or
   released content.
6. Pre-rotation and post-rotation audit chains both verify after key rotation.
7. Retention tests cover every persistent content category, legal hold, bounded
   deletion, backup expiry policy and disposal evidence.
8. Final API and web images and all build/tool images contain no unaccepted High
   or Critical vulnerability.
9. Bandit, Python and Node audits, Gitleaks, TruffleHog, repository quality gates,
   backend tests and frontend tests pass.
10. Backend and frontend retain at least 95 per cent line and branch coverage.

## Non-goals

- This work does not replace the documented requirement for production identity,
  managed secrets, managed object storage, edge HSTS or production infrastructure
  accreditation.
- Local synthetic credentials remain local/test-only and must continue to fail
  production configuration validation.
