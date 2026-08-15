# Development Story

Entries are ordered newest first: the most recent date is at the top of the
file and the earliest is at the bottom.

## 15 August 2026: continuous integration restoration

- Pushing the rebrand revealed that every workflow on main had been failing
  since before the session began. Four inherited faults were fixed: a test
  helper hardcoded Windows drive paths that are relative on Linux; the
  history secret scan flagged Python identifiers as verified Lob secrets;
  the real-browser journey had never passed since the workflow-availability
  gate landed, because no automated topology performed the operator
  attestation; and four backend files had drifted from the canonical
  formatter style.
- One fault was self-inflicted and caught the same day: response payload
  validation had pulled the schema library into the eager bundle, 72
  kilobytes over budget. The validators were rewritten as hand-rolled
  checks and the initial bundle returned under its ceiling.
- The secret-scan gate now fingerprints findings by detector and exact
  matched value rather than by file path, because paths shift with renames
  and checkout depth, which had made one allow-list unable to satisfy scans
  of differing history. Commit-message findings fail closed instead of
  crashing the gate, container validation checks out full history to match
  the CI scan, and the allow-list was regenerated down to seven exact
  entries, each a verified synthetic value.
- The browser topology now deploys and attests the workflow definition
  through the same operations script the local stack uses, keeping the
  fail-closed attestation design while letting the journey run.

## 15 August 2026: rebrand to Mist

- Renamed the product from ISTARI to Mist across application code,
  configuration, scripts, CI and documentation, including the Python package
  (`istari_service` to `mist_service`), the web package scope, Docker image
  names and the Compose project name. Renaming the Compose project means the
  next local start creates a fresh stack; the previous volumes remain on disk
  untouched.
- Three persisted contract identifiers were deliberately kept stable because
  applied migrations write them into the database:
  `istari.workflow-template/v1`, `istari.request-policy/v1` and
  `istari-human-route-v1`. Applied Alembic migrations were not edited.
- Replaced the logo assets with circle-cropped derivatives of the new Mist
  badge and set the sign-in wordmark to render in capitals through CSS so the
  accessible name stays a readable word.
- Replaced the sign-in particle animation with a cloud field: six large
  blurred drifting shapes derived from the theme text colour, animated on
  slow alternating cycles and disabled under reduced-motion preferences,
  which the previous animation did not honour.
- Added a named exceptional band to the line-limit gate: a cohesive file may
  carry an explicit allowlist entry in `scripts/check-file-lines.mjs` up to a
  400-line ceiling instead of being split across files, pinned by the gate's
  own self-tests. The sign-in stylesheet is the first entry.

## 15 August 2026: authentication, object-scope and maintainability remediation

- Closed an authentication regression in public sign-in: the endpoint no
  longer writes account lock fields, so knowing a username could no longer
  revoke a victim's other sessions or block Platform Administrator step-up.
  The lock write now lives behind a step-up-named repository contract, and
  the tests that pinned the old behaviour were rewritten to assert the
  spec's invariant instead.
- Made the shared-pool object-scope policy fail closed. `is_object_scoped`
  now requires explicit route or QC membership evidence instead of granting
  the four routing-pool roles on role alone. Call sites supply a greppable
  evidence marker or the live check result.
- Extracted the triplicated outbox lease-fencing lock and retry backoff into
  one shared module, `workflow_lease_fencing.py`.
- Made concurrent duplicate request submission return the original request
  idempotently instead of an unhandled 500, using a savepoint around the
  insert.
- Tightened two coordination request schemas from extra-ignoring to
  extra-forbidding models.
- Fixed the architecture width checker to count inherited Protocol methods.
  This exposed nine composition-facing union ports over the 12-method
  ceiling, up to 36 methods, now recorded in the shrink-only debt baseline.
- Added frontend runtime validation of request-detail and work-item payloads
  through a new optional parse hook on the API transport; a route-scoped
  error boundary inside the shell so one page crash no longer takes down
  navigation; per-route document titles and focus movement to the main
  region on navigation; focus into the account menu dialog on open;
  conversation polling that now stops on completed requests; and a
  structurally distinct cache key for the paged "my actions" query.
- Corrected documentation: pnpm 10 to 11 in the README, the run-from-source
  command now includes the required env file, AGENTS.md's local-stack
  command now uses start-local.ps1 since a plain compose deploy has no BPMN,
  QC role naming aligned to "QC Manager" across six current guides, and
  single-test guidance added with verified commands.
- Evidence at end of session: 1,323 backend tests passing (13 skipped) at
  98.13 per cent line and branch coverage; 542 frontend tests passing at
  98.81 per cent lines and 95.06 per cent branches; every repository gate
  green.

## 14 August 2026: QA hardening and the SOLID, readability and maintainability programme

- Restored QA readiness on 14 August 2026 after a clean rebuild correctly left
  the seeded workflow unavailable. The exact repository BPMN was deployed and
  checksum-attested, `/ready` returned all four checks as healthy after a
  Camunda restart, and both primary and alternative application routes reached
  QC release and Customer download.
- Replaced startup's host-port dependency with an isolated Compose deployment
  helper. It validates the BPMN, inspects and hashes Camunda's active XML,
  reuses one exact version-1 match, deploys only into empty state, refuses
  conflicts or ungoverned existing state, records the exact deployment identity
  and waits for application readiness. The real QA rerun reused the existing
  definition without creating another version.
- Fixed the routing Overview-to-Queue crash found in live QA. The overview's
  ordinary list and the queue's paginated list had shared one TanStack Query
  cache key, so the paginated observer interpreted summary data as page data.
  Distinct shape-specific keys now preserve broad work-item invalidation, and a
  regression test reproduces the populated CRIOC navigation directly.
- Removed the intermittent workflow and request-detail failures found during
  repeated live route assurance on 14 August 2026. New durable commands give
  their originating API call a five-second dispatch priority window, reconcile
  a competing worker lease from the stored result, and retry one PostgreSQL
  deadlock through the fenced idempotent path. Actor reauthorisation now uses a
  foreign-key-compatible row lock for both workflow finalisation and locked
  detail reads, preventing cycles with notification recipient projection.
- Made absent managed packages and Customer releases explicit nullable results
  for authorised legacy requests, while retaining non-disclosing `404` responses
  for unknown and cross-Customer identifiers. The web panels now select their
  legacy or create-package state without failed-resource console noise. Local
  journey, load and seed tools default to the hardened port-5173 proxy, and
  unexpected API failures emit one content-minimised correlated error event.
- Verified the rebuilt result through five consecutive SYGOC, Nimbus Ops and
  Beacon Team routes and two consecutive CRIOC, JOCK, ACSA-B Ops, SSG Team and
  QC routes, all ending in verified Customer download with no 5xx or deadlock
  log entries. A clean authenticated Customer browser opened the completed SSG
  request with zero console errors or warnings. All 1,168 backend tests passed
  (10 skipped); combined coverage reached 98.68 per cent line and 95.05
  per cent branch. All 424 frontend tests passed at 99.45 per cent line and
  95.02 per cent branch coverage, alongside the repository quality gates.
- Implemented the SOLID, readability and maintainability programme on 14 August
  2026. Executable architecture tests now prevent service-to-infrastructure,
  router-to-persistence, repository-to-service, import-cycle, broad-protocol,
  source-headroom and raw protected-query-key regressions. Every measured debt
  map is empty.
- Split backend use cases behind focused capability ports and explicit
  composition, removed the ORM registration cycle, and decomposed frontend
  session, context, queue, conversation, upload and page orchestration. Every
  maintained source file is below 330 lines and every production frontend
  function is within complexity 12 and nesting depth four.
- Added canonical Prettier and Ruff formatting, a populated PostgreSQL 0043 to
  0047 round-trip gate, and a Chromium-only full workflow lane. The root quality
  gate, strict MyPy over 440 backend modules, Ruff, Bandit, all 1,318 backend
  tests and all 490 frontend tests pass. Backend coverage is 98.73 per cent line
  and 95.00 per cent branch; frontend coverage is 98.8 per cent line and 95.04
  per cent branch. The production web build also passes its initial JavaScript
  and CSS budgets.
- Completed the runtime assurance on the same candidate through the WSL Docker
  integration. PostgreSQL passed populated 0043 to 0047 upgrade, downgrade and
  re-upgrade, a separate empty upgrade and both metadata-drift checks. The run
  found and verified repairs for the 0046 downgrade constraint name, action-view
  unique-constraint metadata and the missing conversation visibility index.
- Passed the complete Chromium journey from Customer submission through CRIOC,
  JOCK, ACSA-B Ops, SSG Team, Analyst production, Manager review, independent QC
  review and release, Customer retrieval and acceptance. Runtime failures found
  during this work led to PostgreSQL-safe product row locking, a correlated
  selected-route membership predicate, mutation-safe conversation composition,
  stable managed-file upload evidence and authoritative product review cache
  updates. The final journey completed without unexpected application HTTP or
  console errors.
- Rebuilt the current documentation authority on 14 August 2026 around the
  executable product rather than retired interface descriptions. The README,
  architecture, workflow, user stories, role matrix, assurance and deployment
  guides now cover dual Customer/Staff contexts, structured request
  conversations, equal assigned-Analyst controls, ordered multi-format packages,
  separate QC review and release, Customer acceptance and the exact current
  technology baseline.
- Expanded the editable Structurizr model with web and API component views, an
  end-to-end request-delivery view and local/private-cloud deployment views. The
  official Structurizr CLI validated the model. Added one detailed Windows,
  Intel and Apple-silicon MacBook, Linux, AWS and Google Cloud host path and a
  gate that rejects stale current-state terms and missing source references.
- Traced the remaining backend warning to a test connection opened against the
  local product-storage adapter's SQLite quarantine index. The fixture now closes
  the connection deterministically, while resource and unraisable-exception
  warnings fail pytest. The complete 1,318-test backend and 490-test frontend
  suites, root repository gate and documentation checks passed.

## 13 August 2026: delivery boards, request tracking and workspace polish

- Separated team delivery boards on 13 August 2026. The always-visible Service
  request board now explains the workflow meaning of every lane, while a
  distinctly labelled Work package Kanban is collapsed by default and loaded
  only when opened. Work packages retain reasoned manual movement and requests
  remain fixed to their named Analyst, Manager, QC and dissemination actions.
- Made internal planning explicit inside the expanded Kanban: Analysts now see
  a prominent `Create internal card` action, create cards owned by themselves,
  and can move cards they own or contribute to without changing the Customer
  request workflow. Managers retain wider team-planning authority.
- Preserved independently filtered totals, paging, table alternatives, saved
  views, WIP controls and fail-closed error recovery for both board types. The
  serialised complete frontend suite passed 394 tests at 99.41 per cent line
  and 95.01 per cent branch coverage, followed by the production build, ESLint,
  line-limit, documentation and terminology checks.
- Reworked Request tracking on 13 August 2026 around one clear operational
  journey. Each request now leads with its current delivery stage, owner and
  next stage; presents the selected route as compact travel history; and gives
  every delivery stage an explicit meaning and `Complete`, `Now` or `Next`
  state without changing the authorised read-only boundary.
- Verified the journey in a real browser at 1720 by 1080 and 390 by 844. The
  narrow view becomes vertical without horizontal scrolling, the browser
  console remained clean, and reduced-motion behaviour is preserved. All 394
  frontend tests passed at 99.42 per cent line and 95.03 per cent branch
  coverage, followed by the build, bundle-budget, ESLint, line-limit,
  documentation and terminology gates.
- Extended the selected route on 13 August 2026 so its journey begins with the
  Customer submission and ends at a larger, dominant `Now · Current owner`
  point. The page names the signed-in viewer and marks `Your unit` only when an
  exact session organisation-unit identifier occurs in the route, without
  inferring membership from display names or changing permissions.
- Rechecked the revised hierarchy in a real browser at desktop and mobile
  widths with a clean console. The complete frontend suite passed 395 tests,
  alongside the build, bundle-budget, ESLint and file-size gates.
- Separated routing-unit obligations from oversight on 13 August 2026. CRIOC,
  JOCK, ACSA-B Ops and every other routing workspace now lead with work that
  needs a routing action, followed by independently collapsed registers for
  active requests routed onwards and completed requests. Passive rows expose
  operational status, owner, required date, age and read-only history without
  granting claim or workflow controls.
- Made Customer acceptance explicit for managed products. Dissemination,
  authenticated artefact access, acceptance and optional feedback are now
  distinct evidence. Only the active originating Customer can accept, retries
  are idempotent, and the hash-linked request history records one attributable
  `PRODUCT_ACCEPTED` event. Approved external HTTPS links remain valid sole
  product artefacts behind existing QC, allow-list, expiry and withdrawal
  controls.
- Verified the routing register in the real local stack at desktop and 390
  pixels with no document overflow and a clean browser console. All 399
  frontend tests passed at 99.42 per cent line and 95.00 per cent branch
  coverage. All 1,022 API tests passed, and the combined coverage confirmation
  reached 98.81 per cent line and 95.03 per cent branch coverage. The complete
  repository static, OpenAPI, operations, documentation and security-oriented
  quality gates also passed.
- Fixed deterministic post-login landing on 13 August 2026. The login boundary
  no longer resumes the protected route that originally opened the sign-in
  screen: every internal role starts at personal Home and Customers start at
  `My requests`. Already authenticated deep links remain available.
- Reproduced the old behaviour with regression tests, then verified admin4 from
  `/tracking` landed on `/overview` and admin2 from `/requests/new` landed on
  `/requests` in the real local browser. A clean authenticated session reported
  no console errors or warnings.
- Polished three workspace surfaces on 13 August 2026. Saved personal profile
  details now render as read-only page content, matching the account details
  section, with an explicit Edit action and a Cancel path back to the saved
  view; the form only appears while the profile is empty or being edited.
  The calendar lost its per-day "Add event" and "+" buttons: each day cell is
  now a single full-cell click target with a hover "+ Add" hint, and the month
  grid is more compact. The work-package Kanban gained a visual refresh with
  rounded columns, count pills and WIP-limit meters, plus clearer drag and
  drop: every valid destination shows a "Drop here to move" zone during a
  drag, invalid columns dim, and hover flicker over child elements was fixed.
  Reasoned move confirmation and the recorded audit trail are unchanged.
- Upgraded the internal work-package Kanban on 13 August 2026. Cards gained a
  quick move menu that reuses the reasoned confirmation dialog, priority
  colouring, formatted due dates, an amber highlight after five days in the
  same state and an iteration chip. The toolbar gained an owner avatar strip
  that toggles the existing owner filter, and a recent internal card activity
  feed now surfaces the audited package history under the board.
- Surfaced the dormant workspace collaboration records API as a team
  noticeboard with pinned links on every workspace Overview. Reads follow
  workspace access; posting and archiving require the existing ROSTER
  management grant and the recorded reasons flow through the unchanged
  audit trail. No backend change was needed; the decision is recorded in
  docs/specs/team-noticeboard-and-pinned-links.md.
- Added a cinematic mist sign-in transition on 13 August 2026, ready for the
  planned rename. Successful sign-in rolls dense white mist over a fixed dark
  backdrop with layered drifting clouds, an animated turbulence wisp filter
  and a centred wordmark, holds while the destination loads, then parts over
  roughly six seconds to reveal the role home or the Customer request
  register. The overlay never covers the classification marking, announces
  "Signing you in" to assistive technology, blocks no input, and collapses to
  a half-second fade when reduced motion is preferred. Verified live against
  the dev stack with the mist clearing onto the Customer's My requests page.

## 12 August 2026: clearer organisation function labels

- Replaced the directory's `Routing function` and `Team staffed` wording with
  `Routing` and `Analysis Team` while retaining an explicit awaiting-staffing
  state.
- Identified QC as a shared function in the directory summary without changing
  organisation, routing, staffing or authorisation data.

## 12 August 2026: calmer assigned-actions view

- Collapsed the complete My assigned actions saved-view, filter and visible-column
  control panel by default, while keeping the authorised action register visible.
- Added focused accessibility coverage for the disclosure's initial and expanded
  states without changing any action-query or authorisation boundary.

## 11 August 2026: one focused team workspace

- Consolidated the role queue and named unit workspace into one primary
  navigation destination.
- Embedded the established actionable queue inside every routing and delivery
  workspace, scoped to the exact authorised unit.
- Removed Planning and Handover tabs and overview panels from the MVP interface.
  Existing service records remain intact and old view URLs return to Overview.
- Reduced overview reads by no longer loading planning or workspace-record
  projections that are not displayed.
- Updated the architecture decision, feature specification, user stories and
  delivery and routing regression coverage.

## 11 August 2026: focused Customer navigation

- Reduced the Customer sidebar to the two destinations used in the request
  journey: `My requests` and `New request`.
- Removed Customer access to the staff personal-calendar and organisation-
  directory pages. A copied direct URL returns safely to `My requests`, while
  staff calendars, team calendars and organisation access remain unchanged.
- Updated the product specifications, user stories, permission matrix and system
  architecture, with regression coverage for both navigation and direct routes.

## 11 August 2026: SOLID and Secure by Design programme completed

- Added executable dependency fitness rules for framework-free domain policy,
  thin business HTTP handlers, repository-owned SQL expression construction and
  repositories that remain independent of FastAPI and the Camunda SDK.
- Split configuration commands into draft, validation, review and activation
  use cases. Split managed-product transfer into grant, byte-transfer and scan/
  promotion coordinators behind the existing public facades and transaction
  boundaries.
- Replaced request and administrative audit hash input with immutable records
  and bounded recursive JSON evidence validation. Added one validated durable
  workflow-start command while retaining the explicit marked-legacy recovery
  path.
- Completed architecture, maintainability and Secure by Design review, with the
  remaining connected-environment controls stated rather than treated as local
  implementation.
- Passed 1,018 backend tests at 98.87 per cent statement and 95.16 per cent
  branch coverage. The bounded-worker frontend suite passed at 99.50 per cent
  line and 95.00 per cent branch coverage. Ruff, MyPy, Bandit, dead-code,
  dependency, documentation, licence, OpenAPI and production-build gates passed.
- Proved controlled local Camunda and PostgreSQL interruption and recovery in
  42.48 and 11.80 seconds respectively, rebuilt the API and worker, and confirmed
  health, readiness, unauthenticated denial and synthetic login behaviour.

## 11 August 2026: typed request and work authorisation

- Replaced repeated request and active-work role, ownership, team, stage and
  assignment combinations with immutable typed domain decisions. Request and
  work services now name the operation being authorised while retaining their
  existing public behaviour.
- Kept PostgreSQL-scoped request and work lookups as a separate enforcement
  layer. The policy therefore protects the use case even if an adapter returns
  too broad a record, while the query boundary minimises retrieved data.
- Added framework-dependency fitness checks plus unit and public API denial
  matrices. Platform support, another Customer, wrong-stage staff, an
  unassigned colleague, an Analyst and a sibling route user receive the same
  concealed response for forbidden and unknown direct identifiers.
- Preserved the distinction between inaccessible objects and invalid workflow
  actions: denials remain non-disclosing `404` responses, while an authorised
  current assignee's invalid action remains a conflict.
- Closed the milestone with 988 backend tests at 98.89 per cent line and 95.08
  per cent branch coverage, without lowering either independent 95 per cent
  gate.

## 11 August 2026: hastener review remediation and transparent history

- Changed the product decision on hastener visibility: the reminder is part of
  the accountable request history, so the Customer and every other user already
  authorised for that request can see it. Notifications remain limited to the
  active assigned Analysts.
- Closed the stale-state race by locking and refreshing the exact assigned
  request before checking its production state and resolving recipients.
- Made the direct `TASK_HASTENER` event mandatory without forcing unrelated
  assignment notifications, and made a successful transaction depend on every
  resolved recipient receiving a projection.
- Added an exact-team board-request read for notification links. It opens rework
  and filtered or later-page requests without relying on the visible board page,
  while inaccessible targets now produce an explicit message.
- Applied message length limits after Unicode normalisation and trimming, and
  retained the same-team People return route when a colleague profile fails to
  load.
- Added regression coverage for disabled notification preferences, exact-link
  scope, hidden lanes, Customer-visible history, Unicode expansion and profile
  error navigation. No database migration or Camunda change was required.
- Closed the remediation with 963 backend tests at 98.89 per cent line and
  95.03 per cent branch coverage, plus 386 frontend tests at 99.50 per cent
  line and 95.00 per cent branch coverage. Repository quality, production
  build, Ruff, MyPy, Bandit, documentation and source line-limit gates passed.

## 11 August 2026: team profiles and accountable task hasteners

- Made every People-register name open a bounded team profile and added an
  explicit route back to the same team's People tab.
- Kept colleague profiles deliberately professional: name, work email, role,
  team position, membership state, rank or grade, skills and account status are
  visible, while service number and free-form personal notes remain private.
- Added Manager-only task hasteners during active delivery. Any current Manager
  in the exact assigned team can remind one active assigned Analyst or the Lead
  and all active Contributors within that team.
- Stored each hastener in tamper-evident request history and sent each recipient
  a content-minimal notification linked to the board item, without changing
  workflow stage, ownership or assignments and without issuing a Camunda
  command. Customer request history filters the internal reminder and its
  recipients on the server.
- Added exact-team, privacy, recipient-resolution, authority, lifecycle,
  notification, navigation and accessibility regression tests and updated the
  current specification, user stories, architecture and threat model.
- Closed the slice with 959 backend tests at 98.89 per cent line and 95.06 per
  cent branch coverage, plus 385 frontend tests at 99.50 per cent line and
  95.01 per cent branch coverage. Repository quality, production build, Ruff,
  MyPy, Bandit, documentation and source line-limit gates all passed.

## 11 August 2026: accessibility navigation and assurance consolidation

- Added a direct accessibility route from the documentation home and master
  plan to the WCAG evidence, completion criteria, production gates and named
  acceptance record.
- Kept the honest assurance boundary: automated axe, contrast, keyboard, focus
  and reflow evidence supports review but cannot replace testing by disabled and
  representative users.
- Combined the aggregate and detailed capability gates into one Definition of
  Done matrix so readers no longer have to reconcile competing completion
  registers.
- Replaced the superseded pilot and expanded-capability templates with one
  current acceptance record covering every role, accessibility review and named
  accountable sign-off.
- Retired the orphaned expansion evidence ledger. Its useful dated migration,
  coverage, workflow, statistics, roster, calendar, board and operational
  results were already preserved in the corresponding 7 August entries below
  and in the current focused assurance records.
- Added the two previously unlisted current specifications to the documentation
  map and retained separate architecture, threat-model, ADR and cloud deployment
  guides where they answer distinct questions.

## 11 August 2026: status presentation fix and SOLID programme begun

- Corrected long workflow status presentation on 11 August 2026. Status pills
  now size to their available column, wrap long text and keep the state marker
  stable instead of covering the current-owner field. The shared component rule
  protects request registers and every other status-pill use consistently.
- Began the SOLID and Secure by Design improvement programme on 11 August 2026
  by extracting one context-managed Camunda runtime. API and worker composition
  now depend on the `WorkflowEngine` port, SDK configuration and lifecycle casts
  remain inside the infrastructure adapter, and startup fails closed without
  leaking a partially constructed engine.

## 10 August 2026: current-state documentation and architecture

- Rebuilt the root README as the plain-English entry point for product users,
  evaluators, engineers, security reviewers and operators. It now covers the
  complete request lifecycle, local setup, cloud sandbox options, security,
  quality gates and all 99 synthetic accounts.
- Added a current user-story catalogue and a dedicated Camunda BPMN guide that
  explain routing, clarification, Lead and Contributor assignment, rework,
  quality review, release, feedback and cancellation without requiring readers
  to understand internal workflow code.
- Added six focused Mist-styled architecture views for system context,
  containers, organisational routing, delivery, durable workflow commands and
  the organisation hierarchy, plus an editable Structurizr DSL workspace.
- Consolidated the documentation around one documentation home, one system
  architecture authority and one complete account directory. Redundant index,
  foundations, account-roster and service-expansion files were retired, with
  links redirected to the current authorities.
- Refreshed the Customer request, Customer dashboard, team Board, team calendar,
  team People, CRIOC workspace and platform administration screenshots from the
  running local application and visually reviewed each image against its current
  documented surface.
- Established the rule that current guides describe only the product a reader
  can use now. Superseded interface and terminology history belongs here, while
  architecture decisions retain only the rationale needed to understand durable
  technical constraints.
- Adopted the public-safe synthetic organisation names CRIOC, JOCK, ACSA-B Ops
  and SSG Team across seed data, workflow labels, application presentation,
  tests, current documentation and diagrams. The previous names remain only in
  this chronological record where they are needed to explain older evidence.
- Incorporated the current accessibility controls for bypass navigation,
  320-pixel reflow, visible focus, target size and automated contrast, and the
  Customer form's four-part progress navigation, completion signals, character
  limits and strengthened validation presentation.
- Passed all 955 backend tests at 98.874 per cent line and 95.016 per cent
  branch coverage, plus all 378 frontend tests at 99.48 per cent line and 95.08
  per cent branch coverage. The repository quality command, production build,
  bundle budgets, documentation duplication and links, terminology, line
  limits, dead-code checks, licences and OpenAPI contract all passed.

## 10 August 2026: sortable people and focused calendar creation

- Turned every organisation People register into an accessible sortable ledger,
  with Managers first by default and deterministic current-history ordering.
- Closed a defence-in-depth gap by requiring a current exact-unit Manager
  membership as well as an active roster grant in FastAPI. A deliberately
  misconfigured Member grant now fails closed, while React also withholds every
  roster control from Members.
- Replaced the permanently expanded calendar form with a centred modal. The
  toolbar Add event control and calendar-day affordances open the same form,
  selected days pre-fill 09:00, failed writes retain context and successful
  creation closes the modal with focus restoration.

## 10 August 2026: lifecycle tracking and analytical graphics

- Reworked the route-scoped tracking register around request titles, linked
  references, current ownership and a graphic view of both organisational route
  and delivery lifecycle.
- Added a dedicated historical detail contract. Exact JIOC (later renamed
  CRIOC), command and Ops route membership is rechecked in PostgreSQL, while
  the read-only response excludes workflow actions, clarification, feedback
  and every product field.
- Added status, due-risk and active-age donut charts plus a median-to-90th-
  percentile stage-duration graphic. Existing scoped API data, legends and
  accessible tables remain the single source of every displayed value.
- Passed all 951 backend tests at 98.26 per cent total coverage and 354 frontend
  tests at 99.47 per cent line and 95.01 per cent branch coverage. Repository
  gates, production build and bundle budget passed. A live JIOC browser journey
  reopened the Russian Troop Movements request from Tracking, rendered the
  read-only lifecycle and displayed the new charts with no console warning or
  error.

## 10 August 2026: action-oriented team workspaces

- Reworked delivery and routing workspace homes around decisions requiring
  attention, rather than duplicating the deeper Statistics page.
- Made Kanban totals independent of cursor pages, focused the default lanes and
  added saved and built-in views, progressive disclosure, a table alternative
  and a shared work-item inspector.
- Connected the daily team surface to clarifications, review, planning freshness,
  blockers, dependencies, capacity, calendars, people, handover and activity.
- Corrected routing queue reads so each selected unit shows only its own current
  decision position.
- Added migration 0030 for bounded self-declared operational skill labels, shown
  only through Profile and an authorised exact-team people projection.

## 10 August 2026: explainable request matching and simpler JIOC routing

- Replaced the misleading title/reference lookup with automatic, explainable
  matching across every Customer-submitted field. PostgreSQL full-text,
  `pg_trgm` and pgvector retrieval feed deterministic field, semantic and
  structured scoring; the interface exposes bounded evidence and never treats
  the score as a duplicate decision.
- Added one transactionally created projection per submitted request and a
  lease-fenced worker indexer. FastEmbed runs a revision and checksum-verified
  `BAAI/bge-small-en-v1.5` model from an offline image cache, so indexing does
  not send request content outside the application and cannot block submission.
- Kept decisions human-led and append-only. JIOC can record possible duplicate,
  related request, existing released product or not-relevant outcomes after
  reviewing the comparison. Every query and save re-applies task ownership and
  route scope.
- Removed the uncontrolled Confirmed category input from the JIOC progress
  contract and interface. Priority and the chosen direct-child route remain the
  only progress values required at that stage; the nullable historical column
  remains for compatibility.
- Built PostgreSQL 17.10 with checksum-pinned pgvector 0.8.1, migrated the
  retained synthetic database to revision 0029 and backfilled all ten requests.
  The worker indexed every projection and a live JIOC API and browser journey
  returned hybrid matches with field evidence. The browser showed no Confirmed
  category field.
- Passed all 936 backend tests at 98.85 per cent line and 95.03 per cent branch
  coverage, plus 327 frontend tests at 99.41 per cent line and 95.03 per cent
  branch coverage. Ruff, MyPy, Bandit, dependency audits and all repository
  gates passed. Refreshed Trivy scans reported zero High or Critical finding in
  each of the API, web, PostgreSQL, Camunda and ClamAV images without an ignore
  file. The API now uses digest-pinned Ubuntu 24.04 with Python 3.12, while the
  PostgreSQL image compiles checksum-pinned pgvector in a discarded build stage
  and runs on Alpine 3.23 without the unused privilege helper.

## 10 August 2026: organisation workspaces, team operations and coordination language

- Completed unified organisation workspaces on 10 August 2026. Effective-dated
  Manager and Member positions now govern every routing and delivery unit. The
  synthetic directory contains 99 named Scottish football identities, with at
  least one Manager and Member in every workspace and the expanded OSG roster.
- Added calendar self-service for all current members, Manager-owned unit events
  and delivery-ticket commitments, and one accountable Lead with up to ten
  Contributors. Only the Lead owns the Camunda task outcome; Contributors gain
  bounded collaboration access without weakening workflow accountability.
- Added routing-specific Queue, Calendar, People, Statistics, Handover and
  Activity surfaces, while delivery teams retain Board and Planning tools.
  Exact-unit and descendant scoping prevents parent, sibling and unrelated-unit
  data leakage. Immutable workspace notes, risks, blockers, decisions and links
  provide a governed operational handover record.
- Closed automated assurance with 922 backend tests at 98.26 per cent coverage
  and 321 frontend tests at 99.40 per cent line and 95.03 per cent branch
  coverage. Ruff, formatting, MyPy, Bandit, npm and Python dependency audits,
  Knip, Vulture, TypeScript, ESLint, repository policy and the production bundle
  budget passed.
- Rebuilt the Compose stack with PostgreSQL 17.10 and Camunda 8.9.14, confirmed
  every service healthy, passed the Camunda route contract and inspected the
  JIOC and OSG workspaces in Chromium. A disposable PostgreSQL database passed
  empty-to-0027 migration, downgrade to 0023, re-upgrade and drift checks.
- Added password assistance and a global visual classification marking on 10
  August 2026. The anonymous flow validates a work email but always returns the
  same accepted result; PostgreSQL source/global limits, per-account suppression
  and content-minimised notifications protect the active Administrator group.
- Added governed unique email to every account and profile. The global marking
  is a versioned singleton, defaults to `OFFICIAL`, and can be changed only by a
  recently elevated Platform Administrator through CSRF, expected-version and
  audit controls. A restrained 22-pixel strip now remains visible above the
  sign-in page and every authenticated workspace.
- Exercised both journeys in live Chromium. A synthetic `admin2` assistance
  request produced the neutral Customer response and the expected mandatory
  account-security notification for `admin1`, without disclosing the submitted
  email in the notification. The Administrator changed the platform to blue
  `OFFICIAL-SENSITIVE`, observed the global confirmation and restored green
  `OFFICIAL`.
- The live PostgreSQL action exposed an enum-name/value mismatch hidden by the
  SQLite unit-test path. SQLAlchemy enum persistence now consistently uses
  declared public values, and a focused regression assertion protects all four
  permitted classification strings.
- Closed the feature with 926 backend tests at 98.84 per cent line and 95.08 per
  cent branch coverage, plus 326 frontend tests at 99.41 per cent line and 95.01
  per cent branch coverage. Ruff, formatting, MyPy, Bandit, dependency audits,
  dead-code, documentation, type, lint, build, bundle and live-runtime checks
  passed.
- Reworked team operations on 10 August 2026 around decisions rather than passive
  navigation. Delivery Managers now land on linked attention, capacity, people,
  calendar, handover and activity signals. Routing units receive a separate
  claim-based decision home. The Kanban defaults to active flow, keeps exception
  and terminal lanes discoverable, exposes complete filtered totals and opens an
  authorised side inspector from either board or table presentation.
- Added exact-unit routing queue reads, operational skill labels and migration
  0030. A live OSG history check exposed that terminal cards could outlive active
  task-based detail access. The request policy now permits history only for a
  current Manager of the exact assigned team, retains concealed denial elsewhere
  and is covered by allow-and-deny regression tests.
- Closed the team-operations candidate with 940 backend tests at 98.88 per cent
  statement and 95.06 per cent branch coverage, plus 337 frontend tests at 99.46
  per cent line and 95.03 per cent branch coverage. All repository gates, static
  analysis, dependency audits, the production build and the live PostgreSQL,
  Camunda, OSG and JIOC walkthrough passed. Route-splitting reduced initial CSS
  from 120.7 KB to 91.3 KB.
- Repaired staff action navigation on 10 August 2026. Operational action cards
  now deep-link to the correct role queue with an exact request selector, while
  Customer actions retain the Customer request detail. The queue fails closed
  when the selected action has completed, moved or left the actor's scope.
- Separated `My actions`, the role-owned queue and the named organisation
  workspace in primary navigation. Shared actions are labelled as available to
  the unit, while claimed work is shown only to its named assignee.
- Added migration 0031 to repair existing links and claimed audiences. A real
  PostgreSQL downgrade and re-upgrade retained the repaired admin4 assignment
  and `/triage?requestId=…` link for Russian Troop Movements.
- The PostgreSQL rehearsal also exposed Alembic attempting unsupported equality
  on `json` defaults. The schema-drift comparator now normalises JSON defaults
  directly while retaining normal Alembic comparison for every other type.
- Verified the reported journey in the in-app browser: admin4 opened Russian
  Troop Movements from My actions and arrived at the selected JIOC routing
  record with the full request, matching evidence and human decision controls.
- Closed automated assurance with 951 backend tests at 98.88 per cent statement
  and 95.06 per cent branch coverage, plus 338 frontend tests at 99.46 per cent
  line and 95.00 per cent branch coverage. Repository policy, static analysis,
  documentation, licence, dependency, production-build, reversible-migration
  and PostgreSQL schema-drift gates passed.
- Reduced previous-request comparison to secondary decision support on 10 August
  2026. The JIOC routing record now shows a collapsed summary by default,
  distinguishes strong matches from lower-confidence suggestions and reveals
  search and evidence only on request. Expanded results remain in a 330 px or
  42 viewport-height keyboard-focusable scrolling region.
- Added regression coverage for collapsed disclosure, honest strong and weak
  summaries, plural and mixed result states, keyboard access, recording a human
  decision and returning to automatic comparison. The frontend closes with 339
  tests at 99.46 per cent line and 95.02 per cent branch coverage.
- Tightened organisation workspace membership and calendar interactions on 10
  August 2026. Every People column now supports accessible ascending and
  descending sorting, with Managers first by default. Roster changes require a
  current Manager position in the exact workspace as well as the roster grant,
  so a stale or misconfigured grant cannot authorise an ordinary Member.
- Replaced the permanently visible calendar form with one central dialog. The
  `Add event` command and every calendar day open that same form, with a clicked
  day pre-populating the start and end date. The dialog restores focus when it
  closes and closes automatically after a successful creation.
- Verified the change with 952 backend tests at 98.87 per cent line and 95.00
  per cent branch coverage, plus 365 frontend tests at 99.51 per cent line and
  95.04 per cent branch coverage. Repository policy, OpenAPI, lint, type,
  security, dead-code, documentation and production-build gates passed. A live
  JIOC Manager walkthrough confirmed the sortable roster and both calendar
  dialog entry points with no browser warnings or errors.
- Removed an identity-authority ambiguity on 10 August 2026. Alan Rough was
  correctly seeded as the JIOC Manager, but the account identity exposed only
  the broad `JIOC Routing User` role. The compact identity now combines role and
  position, while the account details and profile state `Manager in JIOC` and
  name the associated local controls. Server-side membership and grant checks
  remain authoritative.
- Added position-presentation coverage for Manager, Member, mixed, loading,
  unavailable and non-workspace accounts. All 367 frontend tests passed at
  99.51 per cent line and 95.03 per cent branch coverage, together with the
  repository checks and production bundle budget.
- Personalised staff overviews on 10 August 2026 with a first-name greeting and
  distinct personal and organisation workload regions. Aggregate measures now
  name their authorised scope and state that they are not the user's personal
  workload.
- Reordered the primary navigation around the normal operating journey and
  replaced generic sidebar labels with `Home`, `My assigned actions`,
  purpose-specific queues, `Request tracking`, `Operational statistics` and
  `Organisation directory`. Named workspaces now sit next to their queue and
  all destinations retain one deterministic source.
- Covered the new information hierarchy, navigation order, zero and error states,
  QC and Administrator variants and axe semantics. The complete 367-test frontend
  suite passed at 99.52 per cent line and 95.04 per cent branch coverage.
- Made personal calendar visibility explicit on 10 August 2026. New personal
  activity is now visible with detail to the member's exact unit by default from
  either My calendar or the shared workspace. One unchecked `Private
  appointment` control hides the title and notes when deliberately selected.
- Removed the technical three-value privacy selector from creation and rejected
  new availability-only personal writes at the service boundary. Existing
  protected records remain unchanged, shared projections still redact before
  response construction and Manager-only calendar controls remain independent
  from personal sharing context.
- Verified the calendar change with 953 backend tests at 98.87 per cent
  statement and 95.00 per cent branch coverage, plus 368 frontend tests at 99.52
  per cent line and 95.03 per cent branch coverage. The frontend suite includes
  a unit-name lookup failure proving that visibility does not fall back to
  private.
- Refined staff Home pages after representative JIOC feedback on 10 August 2026.
  Removed the direct-child organisation register and its unexpected statistics
  links from Home. Organisation hierarchy comparison remains inside Operational
  statistics.
- Added a responsive quick-access surface generated by the same capability-aware
  navigation model as the sidebar. Each interactive tile explains its purpose,
  excludes the current Home destination and uses restrained entrance, hover and
  keyboard-focus treatment with a reduced-motion fallback. All 368 frontend
  tests passed at 99.52 per cent line and 95.06 per cent branch coverage.
- Replaced the deprecated coordination vocabulary on 10 August 2026 with
  `Incoming requests`, `Request coordination` and `Request Coordination User`
  across React, FastAPI presentation defaults, Camunda task metadata, smoke
  contracts and current documentation.
- Made action ownership route-aware without changing access policy. Shared work
  now resolves its already-authorised unit at read time and displays
  `<unit> · Awaiting owner`; claimed work displays the claimant's name. The
  action summary says `New request requires attention` while preserving stable
  internal action codes.
- Migrated existing scopes, request owners and projection snapshots to revision
  `0032_coordination_language`. The rebuilt local stack retained its data and
  PostgreSQL confirmed the new revision and values.
- Verified 953 backend tests, then the additional defensive ownership branch,
  at 98.87 per cent line and 95.02 per cent branch coverage. All 369 frontend
  tests passed at 99.52 per cent line and 95.06 per cent branch coverage, and
  every repository quality gate passed.

## 9 August 2026: Customer-owned intake and reviewed account requests

- Replaced Customer-facing business-area and recipient-routing questions with a
  comprehensive mandatory requirements form covering the question, outcome,
  context, coverage, urgency, supported activity, required date, delivery form,
  quality criteria, constraints, supporting information and handling needs.
  Internal route selection remains a staff responsibility.
- Added a public, deliberately minimal account-request mode to the login page.
  Customers provide only a display name, work email and access reason. Platform
  Administrators review the request and create the bounded Requester account;
  the public form cannot choose a role, team, scope, username or password.
- Added immutable reviewed-account-request persistence, generic duplicate-safe
  public responses, administrator step-up checks, optimistic concurrency and
  audit records. The service is restricted to local and test environments while
  MVP shared credentials remain an explicitly accepted limitation.
- Added migration 0022 without rewriting sealed configuration history. A real
  retained PostgreSQL 17.10 upgrade and metadata drift check passed after the
  migration correctly preserved that boundary.
- Repaired the retained local environment without bypassing fail-closed
  configuration controls. The guarded start now has complete documented
  settings, least-privilege database identities, enabled local features,
  ClamAV and worker health. Nginx now buffers larger bounded administration
  requests on its isolated writable tmpfs instead of the read-only image.
- Successor proposals derived from historical configurations now replace the
  obsolete fixed intake-field list with the current mandatory Customer contract.
  Historical sealed snapshots remain unchanged and server validation remains
  authoritative.
- Nginx now re-resolves the API service through Docker DNS, so an unchanged web
  container continues proxying correctly after an API recreation. Configuration
  activation also flushes the approved candidate and registry state before its
  immutable evidence row, satisfying the PostgreSQL integrity trigger reliably.
- The independently reviewed successor configuration was activated through the
  browser without editing retained history. John McGinn then submitted a fully
  populated synthetic request, `SR-2026-1C930860`; its outbox event was sent and
  Camunda started the pinned `service-request-v1` revision 1 instance at JIOC
  routing.
- Closed the change with 885 backend tests at 98.82 per cent line and 95.03 per
  cent branch coverage, and the frontend suite at 99.47 per cent lines and
  95.03 per cent branches. Ruff,
  MyPy, TypeScript, ESLint, OpenAPI, policy, documentation, dead-code, licence,
  terminology and line-limit gates passed. The live browser confirmed John
  McGinn's request form blocks incomplete submission and the login page exposes
  the reviewed account-request path.

## 9 August 2026: GitHub quality and Dependabot repair

- Reproduced every repository quality gate locally and compared it with the
  hosted Linux result. The three hosted backend failures shared one cause: a
  Windows-only absolute product-path fixture. It now derives a portable absolute
  temporary path and the focused production configuration suite passes.
- The first repaired Linux run found one final duplicate of that fixture in the
  production API-surface test. It now receives pytest's platform-native absolute
  temporary path as well.
- Aligned dependency automation with GitHub's supported ecosystems by moving the
  backend updater from `pip` to native `uv`, retaining the newest supported pnpm
  major, and adding root Compose and security-tool Dockerfile coverage.
- Added weekly CI, explicit job deadlines, Actionlint, the OpenAPI consumer
  contract and current-source Gitleaks. Coverage and scan evidence are retained.
  The TruffleHog evidence stage now depends on the policy gate, closing a BuildKit
  graph path that could otherwise export raw findings without evaluating them.
- Changed Gitleaks input to an exact tracked-file staging directory. A regression
  proves that even a force-added environment file excluded by both Docker ignore
  policies remains in the scan context, while untracked local files remain absent.
- Extended line enforcement to custom Dockerfiles and the workspace manifest.
  Migration revisions retain their documented line-limit exception. Dependency
  audits now cover locked development and test tooling as well as deployed
  packages; both complete ecosystems reported no known vulnerability.
- Moved Actionlint into a Dependabot-managed Dockerfile. The split container
  workflow now has a conservative cold-run deadline, bounded Docker operations
  and a contract protecting every deployed-image scan/SBOM plus teardown.
- A live root-Compose update found that Dependabot treated locally built image
  tags as private registry dependencies. Those output tags are now explicitly
  ignored while the external Python image remains updateable. A repository
  contract protects that distinction.
- Re-ran the complete hosted suite after the repair. CI, container validation
  and all 13 native Dependabot update jobs passed. The root-Compose log confirms
  it now resolves only the external Python image and no local output tag.

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

## 9 August 2026: Customer workspace refinement and hierarchy-aware statistics

- Refined the Customer workspace on 9 August 2026. Service classification is
  now server-owned rather than Customer input, all remaining intake fields stay
  mandatory, and Customer actions live with their request and notification
  instead of a duplicate staff `My actions` navigation item.
- Replaced ambiguous organisation badges with `Routing function`, `Team staffed`
  and `Team awaiting staffing`. Added a complete profile for every signed-in
  user, including meaningful access, organisation assignment and session data,
  and removed fictional requesting-area scopes from Customer seed identities.
- Closed the refinement with 886 backend tests at 98.22 per cent combined
  coverage and 298 frontend tests at 99.48 per cent line and 95.04 per cent
  branch coverage. Split an overloaded Board scenario, removed unreachable
  protected-route branches and made step-up focus assertions deterministic.
- Added Customer-owned cancellation on 9 August 2026. A mandatory reason,
  optimistic version and locked ownership check atomically close the request,
  local tasks, linked planning packages, capacity reservations and any open
  clarification. A fenced worker then terminates the exact Camunda process and
  safely recovers retries or an already-terminated instance.
- Added bounded self-service profile fields for team or business area, rank or
  grade, service number and additional information. They are isolated from
  governed role, organisation membership and routing, and are returned only by
  the authenticated user's profile endpoint.
- Renamed the Customer register to `Current requests`, added accessible visual
  column headings and changed the public account-request identity label to
  `Name`. The feature includes the accepted ADR, specification and threat-model
  controls for ownership, notification minimisation and Camunda convergence.
- Closed the milestone with 908 backend tests at 98.87 per cent line and 95.22
  per cent branch coverage, plus 302 frontend tests at 99.49 per cent line and
  95.04 per cent branch coverage. Ruff, MyPy, ESLint, TypeScript and source line
  limits passed before the repository-wide operational gates.
- Added hierarchy-aware statistics and role-specific operational overviews on
  9 August 2026. Each query now reauthorises its selected organisation node
  against a single active grant, with explicit parent, sibling and cross-grant
  denials. JIOC and Platform views can drill down through configured descendants,
  command and Ops users remain inside their branch, and Team Managers remain at
  their exact team.
- Kept My actions and My requests transaction-focused. Routing users receive a
  restrained operational landing, Team Managers land on their team Overview,
  QC receives quality and release measures, and Administrators receive platform
  control links. Date presets, adaptive throughput resolution, accessible child
  drill-down, breadcrumb navigation and consolidated suppression messaging make
  detailed statistics easier to read without weakening server-side scope.
- Closed the hierarchy and overview milestone with 912 backend tests at 98.84
  per cent line and 95.09 per cent branch coverage, plus 310 frontend tests at
  99.49 per cent statements and 95.08 per cent branches. Ruff, formatting,
  MyPy, Bandit, dependency audit, Knip, Vulture, ESLint, TypeScript, the
  production bundle budget and every repository quality gate passed. The root
  scripts now invoke the pinned pnpm 10 runtime through Corepack, preventing an
  incompatible global pnpm 11 shim from breaking local verification.

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

## 8 August 2026: configuration governance, maintainability and runtime hardening

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
- Refined the Mist shell with one exact active navigation state, differentiated
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

Mist now projects request events into content-minimised analytics facts and
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

## 7 August 2026: clarification loop, delivery expansion and release-candidate hardening

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
- Seeded 43 deterministic local grants: the named JIOC, command, Ops and shared QC scopes,
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

## 6 August 2026

- Created a clean sibling repository so the mature Coeus codebase and its current
  feature branch remain untouched.
- Audited Mist's login, shell, request dashboard, status journey, work queues,
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
