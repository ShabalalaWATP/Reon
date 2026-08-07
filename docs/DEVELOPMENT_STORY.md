# Development Story

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
