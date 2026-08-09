# Development Story

## 9 August 2026: security remediation and final assurance

- Replaced process-local login throttling with atomic PostgreSQL source and
  global budgets in a cancellation-shielded short transaction, bounded database
  and Argon2 work, and explicit trusted-proxy handling. A real locked-row probe
  failed login closed in 2.49 seconds and recovered after release. The
  product-owner exclusions for synthetic MVP authentication and GitHub branch
  protection remained unchanged.
- Hardened the five runtime images, removed build and unused vulnerable tools,
  applied non-root and least-privilege Compose controls, and separated the
  internal untrusted-content ClamAV daemon from its egress-enabled updater.
  Freshness now uses signed build metadata and proves current definitions are
  loaded.
- Added production documentation-surface controls, response isolation and
  no-store headers, all-image Trivy and CycloneDX CI jobs, exact expiring
  history-scan exceptions, dependency cooldowns and package-source trust
  policy.
- Found model-to-database index and constraint-name drift during the acceptance
  pass. Migration 0021 aligns metadata, downgrades cleanly to 0020, upgrades to
  head and leaves `alembic check` clean. CI now rehearses the latest migration
  in both directions against PostgreSQL.
- Completed current-source Bandit, Semgrep, Gitleaks, TruffleHog, dependency and
  image scans with no accepted high or critical vulnerability. ZAP completed a
  passive web scan and active OpenAPI API scan with no failure.
- Closed the local application gates with 880 backend tests at 98.84 per cent
  line and 95.19 per cent branch coverage, plus 288 frontend tests at 99.49 per
  cent line and 95.06 per cent branch coverage. Fresh QA readiness and two real
  Camunda routes reached release, including clarification loops.

## 9 August 2026: documentation consolidation and current visual record

- Audited the documentation hierarchy and retained specifications, ADRs, threat
  models, runbooks and dated assurance records only where they preserve a
  distinct authority or evidence purpose.
- Removed the superseded executed expansion plan after moving current status to
  the master plan and Product Evolution Definition of Done. Merged the small
  standalone UI-state index into browser evidence.
- Captured and visually inspected four source-controlled screenshots from the
  internally matched synthetic QA Compose application: login, mandatory request
  form, Customer request tracking, and the OSG Team workflow board.
- Added a documentation gate that requires those representative screenshots to
  remain embedded and resolvable, and added a lifecycle index explaining why
  historical assurance records remain.
- Corrected current status references to 73 documented accounts, migration head
  0019 and the latest complete 858-backend/284-frontend regression evidence.

## 8 August 2026: operational coverage and documentation authority

- Clarified that the roughly five-minute backend duration is the complete local
  regression suite, not request-routing latency.
- Added focused tests for every maintenance command route and PostgreSQL grant
  application, including rollback, disposal and fail-closed validation paths.
- Made the organisation and routing document the single complete mock-user
  directory, replaced the duplicate roster with a stable locator, and added a
  seed-to-documentation consistency test.
- Added a documentation-duplication gate and explicitly exempted Markdown
  evidence and specifications from source-code line limits.
- Closed the resulting local gates at 816 backend tests with 99.25 per cent line
  and 95.72 per cent branch coverage, and 258 frontend tests with 99.60 per cent
  line and 95.02 per cent branch coverage.

## 7 August 2026: operational controls and privileged administration delivered

The remaining administrative boundary now uses a five-minute password-confirmed
step-up session for sensitive identity and organisation mutations. The backend
enforces the elevation independently of the React controls and covers expiry,
wrong-password, non-Administrator, CSRF and session-isolation cases. Manual
related-record search and typed links are also complete, with scope, replay,
version and output-release validation and append-only attribution.

Operational readiness now has a bounded dry-run-first retention service,
append-only content-free run evidence, PostgreSQL backup and empty-target restore
scripts, post-restore schema and audit-integrity verification, correlation-safe
structured telemetry and deterministic health alerts covering database, Camunda,
workflow commands, projections, backup age and retention. A support and incident
runbook records pilot hours, severity targets, alert thresholds, recovery,
rollback and safe diagnostics. Live PostgreSQL recovery and named-owner
acceptance remain explicit programme gates.

## 7 August 2026: canonical workforce calendar delivered

Managers and Analysts now use one canonical calendar record across personal
month, week and agenda views and an exact-team shared view. Events support timed
or all-day activity, IANA time zones, daily or weekly recurrence, occurrence
exceptions, future-series splits and reasoned cancellation. Private and
availability-only text is redacted before a team response leaves persistence,
while team-detail events remain visible only inside the exact team boundary.

Exact-team Managers can create shared events and personal commitments. The named
Analyst must acknowledge or dispute a commitment, and an active future commitment
blocks an unsafe roster change. Capacity uses a versioned, expiring preview token
and rejects commit when events or membership change. Higher organisational levels
continue to receive scoped aggregate statistics rather than individual calendar
records.

Migration `0007_canonical_calendar` passed empty upgrade, drift, downgrade to
`0006`, re-upgrade and second drift checks. The complete phase gates passed at
506 backend tests (97.30 per cent line, 95.34 per cent branch) and 176 frontend
tests (99.42 per cent line, 95.05 per cent branch), with clean Ruff, mypy,
TypeScript and ESLint checks.

## 7 August 2026: effective team rosters delivered

Every seeded team now has an authorised workspace boundary backed by an
effective-dated membership timeline. Exact-team Managers can add an existing
unassigned Analyst, schedule a transfer from another team or end an eligible
membership with mandatory evidence. Analysts receive the same current and
historic roster picture without management controls or change reasons.

Membership changes lock the subject account, enforce one open timeline, use
expected versions and reject cross-team or stale authority. Active service work
blocks removal or transfer. Scheduled changes update the compatibility
projection, staffing status and session scope when they become effective, while
immutable metadata activity retains the audit trail. Platform Administrators
remain the only users able to create identities or change account roles.

Migration `0006_team_memberships` passed empty upgrade, drift, downgrade,
re-upgrade and second drift checks. The complete gates passed at 482 backend
tests (97.61 per cent line, 95.00 per cent branch) and 166 frontend tests (99.41
per cent line, 95.25 per cent branch). Board, Calendar and Planning tabs remain
honest foundation states pending their dedicated expansion phases.

## 7 August 2026: scoped operational statistics delivered

ISTARI now projects request events into content-minimised analytics facts and
serves operational statistics only through audited, action-specific management
grants. JIOC, command, Ops and Team managers receive the appropriate exact or
descendant scopes, while the Platform Administrator receives whole-platform
aggregates without request or product content. Cross-branch, ancestor, sibling,
expired and revoked access paths are covered by API tests.

The React statistics workspace uses grant-aware navigation and exposes traffic,
work in progress, age, due risk, throughput, stage duration, clarification,
rework, feedback and direct-child comparisons. Each visual has an equivalent
accessible data table, projection freshness is explicit and feedback ratings are
suppressed for cohorts smaller than five. The full backend and frontend coverage
gates remain above 95 per cent for both lines and branches.

## 6 August 2026

- Created a clean sibling repository so the mature Coeus codebase and its current
  feature branch remain untouched.
- Audited ISTARI's login, shell, request dashboard, status journey, work queues,
  theme tokens and sixteen Scottish-player mock identities.
- Chose selective visual reuse rather than a whole-product rename because the
  original domain is deeply embedded across routes, permissions and workflow code.
- Established the visual thesis: dark graphite service workspace, restrained cyan
  hierarchy, mono request references and reduced-motion-safe ambient effects.
- Replaced conversational intake and domain-specific routes with a structured form,
  Customer dashboard and one human-led service-delivery workflow.
- Verified Camunda 8.9.14 as the latest stable patch on the research date, and
  selected PostgreSQL 17 plus the V2 API and official async Python SDK.
- Recorded the workflow authority, outbox, identity, licence and production gates
  before implementation began.
- Reviewed the supplied MVP definition as a sensitive reference without copying
  it into the repository or retaining derived renders in the workspace.
- Expanded the product plan with drafts, recorded human related-work checks,
  operational notes, workload visibility and a supporting administrator role.
- Added measurable foundations for object-level access, tamper-evident audit,
  accessibility, performance, recovery, observability and pilot exit decisions.
- Established pragmatic SOLID boundaries so domain policy and use cases remain
  independent of HTTP, database, workflow-engine and UI frameworks.
- Reworked claim and completion into durable, leased outbox commands with a
  second final-boundary authorisation check and exact Camunda-state recovery.
- Added SQL-scoped work queries so role, Customer, team and Analyst filters
  are applied before rows leave persistence.
- Replaced the generic single-team assumption with a selectable hierarchy rooted
  at JIOC. Every seeded sibling became a first-class selectable route. At this
  stage OSG was the only staffed team and other destinations waited visibly.
- Corrected the post-delivery path to Analyst → Team Manager → QC Manager →
  authenticated Customer download. JIOC, command and Ops users track progress
  after routing but do not approve the product.
- Added the complete 40-unit, data-driven organisation tree with stable IDs,
  retired-reference handling and unit-specific Camunda candidate groups. All
  direct children remain selectable; only OSG Team is initially staffed.
- Added the authenticated organisation tree, membership-scoped metadata tracker
  and contextual route selectors to the React workspace, with accessible error
  relationships and no content leakage through tracking.
- Proved two independent routes against live Camunda 8.9.14: the staffed
  DIGOC → NCGI-A Ops → OSG Team journey completed through dissemination, while
  SYGOC → Nimbus Ops → Beacon Team stopped at the exact unassigned Team Manager
  task with no invented Beacon users or OSG fallback.
- Enabled Camunda business-ID uniqueness and fenced command leases and
  reconciliation so duplicate starts, stale dispatchers and stale engine
  observations cannot overwrite newer workflow truth.
- Completed a real React, FastAPI, PostgreSQL and Camunda browser journey with the
  Scottish-player identities from Customer submission through JIOC, command, Ops,
  OSG Analyst production, Manager check, QC dissemination, authenticated download
  and one-time feedback.
- Corrected the queue boundary discovered by that journey: unclaimed tasks now
  expose only claimable metadata, request content loads after ownership, and a
  completed task no longer triggers an avoidable unauthorised detail refetch.
- Closed the final API security review findings by row-locking current membership,
  user, task, request and released-product scope at the final read or workflow
  boundary. Kept database-level append-only audit grants visible as a pilot gate
  instead of overstating the local runtime role.
- Expanded the synthetic roster to 72 sequential `adminN` accounts. Every team
  now has its own Manager and Analyst, while OSG has three Managers and seven
  Analysts for the initial operational audience.
- Replaced the unstaffed Beacon smoke with a complete SYGOC → Nimbus Ops → Beacon
  Team journey using Beacon's distinct Manager and Analyst candidate groups.
- Added bounded local Platform Administration for account provisioning, profile
  and membership maintenance, reversible deactivation and organisation display
  names. Kept the administrator outside all service-request content paths.
- Added owner-isolated Customer drafts with optimistic version checks and an
  atomic, retry-safe transition from a draft into a submitted service request.
- Made final submission business fields and decision evidence authoritative in
  both the React and FastAPI boundaries, with an accessible error summary and
  deterministic invalid-field focus.
- Added released-product links and feedback state to the Customer register, and
  required a one-time rating with a meaningful comment after release.
- Rehearsed the new schema from an empty database and across a downgrade and
  re-upgrade from the previous revision. Formatting, lint, types, builds and both
  independent 95 per cent coverage gates passed for the expansion slice.

## 7 August 2026

- Added a distinct production clarification loop so an assigned Analyst can ask
  the Customer a mandatory question with reason and response deadline before
  submitting a product from either in-progress or rework states.
- Stored each exchange as an ordered PostgreSQL thread with immutable actor and
  assignment snapshots, optimistic version checks, one-open-thread enforcement
  and explicit answered or withdrawn outcomes.
- Limited full clarification content to the originating Customer, assigned
  Analyst and exact Team Manager. Routing trackers receive only the waiting
  status and timing metadata, and Platform Administrators remain outside the
  request-content path.
- Added the Customer `Needs your input` journey and structured Analyst and
  Customer controls, including repeated exchanges, withdrawal and history in the
  request dashboard.
- Versioned the Camunda process without changing its stable process ID. Customer
  responses return directly to the same delivery-team Analyst without adding
  command or Ops approval steps.
- Extended the executable smoke to prove two consecutive clarification loops,
  retention of the same OSG Analyst, final Manager and QC review, dissemination,
  and a separate staffed SYGOC route on Camunda 8.9.14 with PostgreSQL secondary
  storage.
- Removed residual domain-specific wording from active product surfaces and made
  the terminology gate reject it in future application and workflow changes.
- Closed the slice with 462 backend tests at 99.10 per cent line and 96.22 per
  cent branch coverage, 158 frontend tests at 99.30 per cent line and 95.31 per
  cent branch coverage, and passing static, build, migration and workflow gates.
- Added explicit, independently actionable management grants for statistics,
  roster, calendar, board and capacity. Grants are time bounded, versioned,
  reasoned, revocable and separate from workflow roles and team membership.
- Seeded 42 deterministic local grants: the named JIOC, command and Ops scopes,
  plus exact-team authority for every active Team Manager. Re-seeding preserves
  later grant changes rather than silently restoring authority.
- Added a transactionally rebuilt organisation closure with self, ancestor and
  descendant paths, and rejected cycles or missing parents before scope data can
  be used.
- Added content-free request facts and stage intervals that retain only route
  unit IDs, dates, states, timings, counts and rating values. Request narrative,
  Customer identity, product content, clarification text and feedback comments
  do not enter the analytics tables.
- Connected projection refresh to the append-only request-event boundary, with
  deterministic rebuild and freshness state, so a dashboard read never needs to
  cross into request-content storage.
- Proved exact, descendant, ancestor, sibling, wrong-action, inactive, expired,
  revoked, stale-version and supersession behaviour, including tamper-evident
  administration audit records.
- Rehearsed migration 0005 from empty and previous revisions with two clean drift
  checks. The slice closed with 471 backend tests at 99.18 per cent line and
  96.54 per cent branch coverage.
- Added exact-team workspaces with Overview, Board, Calendar, People, Planning and
  Activity areas for every staffed team. Managers can add an existing Analyst,
  end membership or schedule a transfer, while Platform Administrators retain
  global account and role control.
- Implemented one canonical workforce calendar with month, week and agenda views,
  recurrence, privacy levels, personal commitments, acknowledgement and dispute,
  and versioned calendar-backed capacity previews and reservations.
- Added workflow-derived board and table views. Service-request movement remains
  a named Camunda action, while separately versioned work packages support WIP
  limits, saved filters, keyset pagination, dependencies, immutable activity,
  iterations and safe Manager-led reassignment.
- A real-browser Manager journey found a workload projection gap: roster safety
  counted active service requests but not owned work packages. The repository now
  combines both sources, and browser proof showed the active-work count and
  membership-removal guard move to the replacement Analyst during handover.
- Closed the aggregate application gates at 513 backend tests with 99.59 per cent
  line and 97.48 per cent branch coverage, and 183 frontend tests with 99.41 per
  cent line and 95.15 per cent branch coverage. Static checks, the production
  build, dependency audits, Bandit, BPMN validation, the workflow contract and
  Compose configuration also passed.
- Kept pilot readiness open. Docker Desktop rejected the Windows bind mount for a
  fresh PostgreSQL and Camunda board walkthrough, so that full current topology,
  backup and restore, manual accessibility, performance, recovery and stakeholder
  sign-off remain assurance work rather than being inferred from unit tests.
- Restored the complete Docker topology and completed a real Customer-to-release
  browser journey through JIOC, DIGOC, NCGI-A Ops and OSG Team. The Customer
  answered an Analyst clarification, downloaded the released product and gave
  required one-time feedback from the tracking dashboard.
- Completed an alternative SYGOC, Nimbus Ops and Beacon Team route through the
  application, PostgreSQL and Camunda, proving selectable non-OSG teams retain
  distinct candidate groups and real Scottish-player staffing.
- Exercised scoped statistics, roster history, Manager membership changes,
  calendar, board and planning workspaces in the browser. Current Chrome, Edge
  and Firefox checks covered desktop and narrow layouts, with zero axe findings
  on named pages and keyboard and reduced-motion review.
- Used controlled Camunda and PostgreSQL interruptions to find and fix two
  recovery defects: retry exhaustion during an outage and readiness returning
  500 while the database was unavailable. Recovery is now bounded, explicitly
  requeueable by exact failed request and records append-only evidence.
- Added a reproducible authenticated load runner. The first local read rehearsal
  completed 240 requests with zero errors and 232.02 ms p95, establishing the
  baseline used to prepare the later agreed-scale rehearsal.
- Scanned both application images. The API was clean; the initial web image had
  11 high Alpine findings with available fixes. The runtime now applies security
  upgrades during the build and the rebuilt web image is clean at high and
  critical severity.
- Added reproducible, digest-pinned source secret scanning and retained the empty
  machine-readable result. Inspected a captured live API log stream for known
  synthetic request, clarification, product, feedback and authentication values;
  none appeared.
- Retained versioned Chrome, Edge and Firefox traces for the mandatory Customer
  form, tracking dashboard, released-product download and clarification and
  feedback history. Separate Chrome traces cover Manager workspaces, Platform
  Administration and JIOC-scoped tracking and statistics.
- Seeded a temporary, self-verifying performance dataset of 250 active users,
  5,000 calendar occurrences and 2,500 OSG work packages. The first scaled
  diagnostic exposed an N+1 package reader and high-frequency session-row writes.
- Replaced package list N+1 reads with a bounded bulk projection, made the async
  PostgreSQL pool explicit and throttled `last_seen_at` persistence while still
  validating every request and preserving the configured idle timeout.
- The corrected 50-user rehearsal passed after a two-minute warm-up and ten
  steady-state minutes: 47,154 requests, 945.29 ms p95, 1,114.85 ms p99 and
  0.002 per cent unexpected errors. The pre-scale database snapshot was restored
  and verified, leaving no performance identities, packages or calendar events.
- Re-ran the high and critical image gate against the refreshed vulnerability
  database. It exposed newly reported 2026 findings in the Debian 12 API base,
  including a critical zlib finding. Replaced that runtime with digest-pinned
  Python 3.12 on Alpine 3.23, rebuilt the image and proved both API and web
  images clean at high and critical severity. The replacement API container is
  healthy against the restored database.
- Closed the final automated application run at 550 backend tests with 98.87 per
  cent line and 95.38 per cent branch coverage, and 188 frontend tests with
  99.43 per cent line and 95.04 per cent branch coverage.
- Completed a fresh state-changing Edge journey through JIOC, DIGOC, NCGI-A Ops
  and OSG Team, including Analyst clarification, Manager and QC review,
  authenticated download and feedback. Repeated the full route in Firefox
  through SYGOC, Nimbus Ops and Beacon Team with that team's own Manager and
  Analyst. PostgreSQL and Camunda reconciliation confirmed both workflows and
  products completed with no branch fallback.
- Added a hash-verifying report renderer and retained final HTML and JUnit
  artefacts. Together with the existing Chrome Manager, statistics, roster,
  calendar, board and Administrator traces, this closes the technical browser
  and all-journey evidence gates. Human acceptance remains explicitly separate.
- Re-audited the prospective Git baseline before committing. A fresh secret scan
  correctly exposed that generated Playwright browser profiles were entering the
  generic Docker build context and that the application-image ignore policy was
  too broad for assurance scanning. Added a dedicated secret-scan inventory that
  includes documentation and tests while excluding generated state, then reran
  digest-pinned Gitleaks across 2.71 MB of source with no finding.
- Created the local root commit only after staged-file and generated-artifact
  review. The first TruffleHog history scan identified six verified Lob-detector
  false positives caused by test names that were exactly 40 characters long.
  Renamed the tests, reran all 550 backend tests and amended the unpublished root
  commit. Digest-pinned TruffleHog then scanned 513 chunks and 2,828,642 bytes of
  reachable history with zero verified or unknown finding.
- Published the reviewed baseline to the Repository Owner's explicitly selected
  public `ShabalalaWATP/Reon` remote. The first hosted run exposed a missing `uv`
  setup in two Linux jobs and a timezone-dependent frontend assertion. Corrected
  both cross-platform issues and pushed commit `47a0a6b`. GitHub Actions run
  `31169475483` then passed every application, CodeQL, secret, dependency,
  licence, PostgreSQL, container, Trivy and bounded Camunda job.
- Defined the next product expansion without relabelling it as existing
  capability. The specification and implementation plan were subsequently
  accepted for implementation and cover personal
  action workspaces, durable notifications, securely scanned PDF, DOCX and PPTX
  products or approved HTTPS links, versioned organisation and bounded workflow
  configuration, planning enhancements and further scoped statistics. The plan
  keeps human routing, immutable in-flight versions and the completed MVP
  evidence intact.
- Implemented that expansion as a local release candidate behind independent
  production-off feature flags. The application now provides a role-scoped
  personal action workspace, durable notifications, private managed PDF, DOCX
  and PPTX dissemination or safe approved HTTPS links, effective-dated
  configuration, a richer planning cockpit and exact-grant scoped statistics.
- Hardened managed-product delivery through bounded upload intents, signature
  and Office-package validation, defence-in-depth ClamAV scanning, private
  storage, immutable review evidence, authenticated Customer downloads and
  audited redirects. End-to-end HTTP tests found and fixed an ASGI replay defect
  that could cancel streamed downloads.
- Pinned both the Camunda process identifier and exact approved process version
  at direct and draft request submission. Review also added request-row
  serialisation for concurrent pins, rejected unavailable workflow definitions
  and enforced Draft immutability at the repository boundary.
- Independent review then found six cross-slice blockers that focused tests had
  missed: unavailable baseline pinning, split dissemination state, invalid retry
  upload grants, frontend flag drift, metadata-only configuration and empty
  production statistics. The fixes now preserve legacy mode, fail readiness
  closed when configuration is enabled, bind workflow starts and routing to
  immutable pins, materialise new stable teams, use exact dissemination evidence,
  gate the React app by authenticated capabilities and project content-free facts.
- Closed the corrected local release-candidate gates at 775 backend tests with
  98.92 per cent line and 95.04 per cent branch coverage, and 243 frontend tests
  with 99.54 per cent line and 95.05 per cent branch coverage. Ruff, MyPy, ESLint,
  TypeScript, production build, Bandit, dependency, licence, terminology,
  line-limit, Compose configuration and SQLite migration rehearsal also pass.
- Final independent review fixed optimistic-version hand-off across managed-file
  upload stages, enforced QC authorisation before dissemination replay, retained
  completed legacy product downloads alongside managed releases, made stable
  team identity authoritative after configured renames, and bound workflow starts
  to attested immutable process identity. Both the code-quality and defensive
  security rechecks reported no remaining P0, P1 or P2 blockers.
- Kept production and acceptance claims separate. Live PostgreSQL concurrency,
  deployed Camunda sibling routing, target object-store/scanner operation,
  multi-browser, load, recovery and named product, security, operational and UAT
  acceptance remain open in the product-evolution Definition of Done matrix.
- A subsequent whole-product defect review hardened the release candidate at its
  trust boundaries. Managed withdrawal is now authoritative over legacy product
  access, cancelled or completed requests cannot mutate drafts, QC dissemination
  is hidden until its workflow stage, and revised packages can start after rework.
- Configuration activation now rebuilds organisation closure, restart restores
  the immutable active projection instead of reseeding fixtures, and future-dated
  moves and retirements preserve their current routes until effective. New Team
  Managers receive audited exact-team grants which are revoked on role, team or
  status changes.
- Workflow dispatch now verifies the engine-returned process identity, recovers
  only explicitly retryable exhausted commands, supervises maintenance failures
  and fails readiness closed after repeated faults. Backup and restore scripts
  use protected temporary libpq service files so database passwords do not appear
  in child-process arguments, and the expected revision follows the actual head.
- Reframed configuration administration around the current configuration and
  proposed changes without weakening immutable revision, independent approval or
  in-flight pinning controls. New proposals refresh and select consistently.
- Added literal organisation search with ancestor context, a selected-path
  breadcrumb and effective structurally valid parent filtering for create and
  move operations. Repeated same-proposal moves no longer create zero-length
  hierarchy edges.
- Made impact preview semantic: reminder schedules are canonical and unchanged
  staffing shortfalls remain validation findings rather than invented changes.
- Added complex configuration and routing stories, ADR 0018, expanded threat
  controls, a role/permission matrix, configuration runbook, audit catalogue,
  assurance record and an honest enterprise-readiness gap register.
- Closed the local regression gates at 790 backend tests with 98.88 per cent
  line and 95.03 per cent branch coverage, and 250 frontend tests with 99.55
  per cent line and 95.01 per cent branch coverage. The rebuilt-stack Chromium
  journey confirmed the revised terminology, unchanged preview, contextual
  search, breadcrumb and exact-kind parent choices. The step-up form now exposes
  its signed-in account to password managers without displaying another field.
- Rechecked scheduled behaviour and fixed three approval-risk defects: temporary
  scheduled changes now show their restoration, retirement removes later route
  entries, and semantically unordered template fields produce one canonical
  approval digest.
- Added exact snapshot evidence to approvals and activations. New pins and
  readiness now recompute it, PostgreSQL blocks reassignment of sealed
  components, and approved workflow process identity and checksum are immutable
  while operational deployment availability remains separately controllable.
- Reworked first-start configuration seeding so a fresh PostgreSQL database uses
  proposed changes, validation, independent approval and activation rather than
  bypassing lifecycle guards. An isolated empty-to-0018 rehearsal produced equal
  non-zero digests and denied runtime attempts to alter sealed ownership or
  approved workflow identity.
- Kept legacy upgrades honest. A pre-0018 imported baseline without independent
  evidence fails readiness closed and must be superseded through the governed
  flow. The migration and operations documents explicitly forbid invented or
  backdated approval evidence.
- Expanded enterprise foundations with requirement-level story traceability,
  configuration action permissions, audit limitations, operations and recovery
  threats, a business-continuity framework, enterprise documentation index and
  unsigned Product Evolution acceptance record. Routing-stage search and path
  confirmation remain clearly specified follow-up work, not a current claim.
- Closed the final local gates at 804 backend tests with 98.88 per cent line and
  exact 95.02 per cent branch coverage, and 257 frontend tests with 99.60 per
  cent line and exact 95.02 per cent branch coverage. Ruff, MyPy, Bandit,
  TypeScript, ESLint, build, OpenAPI, Camunda smoke, BPMN mutation, terminology,
  licence and line-limit gates all pass.
- Strengthened configuration evidence on 8 August 2026. PostgreSQL now rejects
  structurally forged approval and activation inserts, while runtime readiness
  independently checks actor status, separation, reviewed revision, activation
  lineage and digest equality. A fresh empty-to-0018 PostgreSQL exercise seeded
  all 73 users and matching non-zero evidence, then denied both forged event
  types. A scheduled rename ending when retirement begins now reports the
  remaining difference instead of falsely claiming a return to current.
- Kept enterprise claims bounded: administrator search, breadcrumbs and parent
  filtering are implemented, while routing-user path confirmation and bounded
  destination search remain explicitly not implemented. Added representative
  UAT scenarios, an enterprise documentation index, readiness gaps, audit
  catalogue, continuity framework, role matrix and updated threat controls.
- Added native routing-user orientation without changing human accountability.
  The API now exposes only the selected pinned path and authorised direct
  children; the React control adds literal name/code filtering and an announced
  selected-route summary, with no ranking, recommendation or fallback.
- Refined the ISTARI shell with one exact active navigation state, differentiated
  hover and keyboard focus, stronger readable statuses and an account menu that
  exposes the active account, role, scope and session expiry. Desktop and
  640-pixel browser inspection confirmed focus visibility, route-close behaviour
  and popover containment.
- Added presentation-only service age, waiting and required-date indicators to
  Customer registers, request context and staff queues. These values use stored
  timestamps and never alter Camunda state, priority, ownership or notifications.
- Passed 816 backend tests at 99.24 per cent line and 95.66 per cent branch
  coverage, and 279 frontend tests at 99.59 per cent line and 95.02 per cent
  branch coverage. Ruff, MyPy, TypeScript, ESLint, build and documentation gates
  also remained clean.
- Rehearsed both workflow routes on PostgreSQL-backed Camunda 8.9.14. Controlled
  Camunda and PostgreSQL interruptions returned safe 503 readiness responses,
  recovered in 23.24 and 14.46 seconds respectively, and retained the exact
  completed process. One transient post-restart claim was recovered by the
  outbox; the next complete application journey passed with zero residual
  command or workflow errors.
- Preserved the long-lived QA configuration when the current code correctly
  rejected its pre-sealing baseline. A separate empty target project migrated,
  seeded, received explicit workflow availability attestation, completed the
  SYGOC, Nimbus Ops and Beacon Team journey, and returned JIOC plus only DIGOC,
  SYGOC and MYGOC in the native routing workspace. Its disposable volumes were
  removed after evidence capture.
- Completed a maintainability and portable-evaluation pass on 8 August 2026.
  Recurring Knip and Vulture gates now detect frontend and backend dead code,
  including exports referenced only by tests. Confirmed dead helpers and a
  redundant completion-validation layer were removed while authoritative
  transaction-boundary checks remain.
- Replaced per-request configuration-policy loading with bounded batches and
  skipped mutable organisation queries for fully pinned routes. Completed
  history no longer mounts release lookups while collapsed, board dependencies
  retry coherently, and calendar rendering reuses formatters and groups events
  in one pass.
- Corrected local BPMN availability attestation to execute inside the API
  container and added a behavioural PowerShell contract for arguments, failure
  propagation and working-directory restoration. Compose now forwards the
  documented database-pool, session, elevation and process settings.
- Tightened production PostgreSQL validation to asyncpg-compatible
  `ssl=verify-full` and added a dialect-level regression test. Runtime readiness
  now validates the active sealed configuration regardless of whether its
  administration surface is enabled.
- Added a documentation map, detailed current system architecture,
  configuration and release references, explicit production gates and complete
  local Docker/source instructions. Private AWS/SSM, Google Cloud IAP/SSH and
  Azure Bastion/SSH guides cover synthetic VM evaluation; Kubernetes remains an
  explicitly unimplemented production target under ADR 0019.
- Added automated relative-link and long-form duplication checks, marked stale
  candidate measurements as historical, and retained ADRs, threat models and
  assurance evidence for traceability rather than deleting them.
- Closed the milestone with 818 backend tests at 99.25 per cent line and 95.66
  per cent branch coverage, and 280 frontend tests at 99.60 per cent line and
  95.04 per cent branch coverage. Repository policy, Ruff, MyPy, Bandit,
  dependency audit, TypeScript, ESLint, production build, OpenAPI, Camunda
  contract, documentation, terminology, licence and line-limit checks passed.
- Completed a second simplicity and efficiency review on 8 August 2026. The
  review distinguished safe simplification from changes needing concurrency or
  recovery design, rather than treating cyclomatic scores as refactoring goals.
- Split top-level and heavy Team workspace routes, added a manifest-based entry
  budget and reduced the common JavaScript entry from 457.15 kB to 214.89 kB.
  Static entry assets now measure 300,068 bytes JavaScript and 95,306 bytes CSS.
- Replaced notification recipient and state N+1 reads with bounded set queries,
  one recipient flush and one checkpoint refresh per selected event batch.
  Unchanged configuration restoration now preserves unit versions and identical
  closure rows.
- Corrected filtered-route selection visibility, cross-occurrence calendar form
  state and UTC-derived browser date defaults. Removed a speculative planning
  event port and unused repository methods, and moved the in-memory product
  storage fake out of the production package.
- Recorded the higher-risk next work explicitly: per-request membership
  reconciliation, external I/O under database locks, unbounded feeds, Board
  database pagination/WIP concurrency, maintenance replica coupling and dense
  frontend module boundaries.
- Reviewed every backend cyclomatic hotspot rather than treating its score as a
  refactoring target. One notification mapper was reduced to data tables; the
  eight remaining findings represent explicit security, composition, parser,
  invariant or transition rules, with configuration composition retained as a
  future responsibility-based split.
- Closed the second pass with 824 backend tests at 98.70 per cent total coverage
  and 283 frontend tests at 99.60 per cent statements and 95.09 per cent
  branches. Static repository gates, Ruff, MyPy, Bandit, formatting and the
  production build with its entry budget all passed.
- Implemented the accepted runtime-hardening findings on 8 August 2026, with
  atomic concurrent Board WIP enforcement intentionally excluded. HTTP sessions
  no longer reconcile membership timelines; a separately deployable worker now
  owns due projection, outbox and reconciliation jobs under renewable named
  leases and a durable readiness heartbeat.
- Split workflow commands, managed upload/scanning and download streaming into
  short database phases around external I/O. Owner/generation fencing and fresh
  authorisation prevent a stale worker or transfer from projecting a result,
  while connection probes prove storage, scanners and slow stream chunks hold no
  request database connection.
- Added database-filtered keyset pages for Customer requests and drafts, staff
  work, tracking, administrator users, older request history and the mixed
  Board. Matching indexes include a scope-first route index found during real
  plan inspection. React appends pages and resets them with filter changes.
- Split broad backend repositories, API contracts/clients, Work Package fields,
  work-action fields and queue detail/list rendering by responsibility. The
  source line gate remains green without weakening behaviour or type contracts.
- Migrated and seeded a clean PostgreSQL 17.9 target with 2,500 rows per bounded
  feed, 2,500 packages, 5,000 calendar records and 250 users. First and deep
  statement counts matched, every index plan passed and overlapping workers ran
  one callback. A 2,500-request HTTP run returned no errors at 473.19 ms p95;
  production-built Playwright journeys retained second pages for Customer,
  routing, Board and administrator views. Disposable containers were removed
  after hashed evidence capture.
- Closed the runtime-hardening milestone with 858 backend tests at 98.83 per
  cent line and 95.18 per cent branch coverage, plus 284 frontend tests at
  99.49 per cent statements and 95.06 per cent branches. A separate backend
  branch gate exposed and corrected the previous combined-percentage blind
  spot. Board queries, worker lifecycle and product transfer phases now have
  explicit cursor, fencing, retry, cancellation and stale-state regressions.
- Passed Ruff, formatting, MyPy, Bandit, Vulture, Knip, TypeScript, ESLint,
  production builds, terminology, documentation, operations-contract, licence
  and Python/Node dependency gates on the final runtime-hardening source. The
  current dependency audits reported no known vulnerability.
