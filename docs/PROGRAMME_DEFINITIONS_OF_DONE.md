# ISTARI Service Expansion: Definitions of Done

## Purpose

These definitions govern the expansion programme covering Customer data quality,
production clarification, scoped operational statistics, team administration,
workforce calendars and agile delivery workspaces. A passing unit test or a
rendered page is not sufficient evidence of completion by itself.

The programme remains open until every phase definition below is satisfied and
the final completion audit can point to authoritative evidence for every item.

The executable acceptance register is
[Definition of Done Matrix](assurance/DEFINITION_OF_DONE_MATRIX.md). Each gate
has a stable identifier, an objective pass condition, a reproducible command or
review method and a required evidence artefact. The prose in this document
defines the standard; the matrix proves whether the standard has been met.

## Evidence state rules

Every gate uses one of these states:

- `OPEN`: work or authoritative evidence is missing;
- `IN PROGRESS`: implementation or verification is under way;
- `EVIDENCE READY`: the technical evidence passes but an explicitly named human
  acceptance is still outstanding; or
- `ACCEPTED`: every stated condition and required acceptance is complete.

Only `ACCEPTED` closes a gate. A unit test cannot substitute for a real browser
journey, SQLite cannot substitute for a PostgreSQL-specific check, a workflow
fake cannot substitute for the required Camunda proof, and an automated
accessibility scan cannot substitute for the stated keyboard and zoom review.
Evidence records include the date, environment, exact command, tool version,
result, artefact path and reviewer where a review is required.

## Quantitative pilot thresholds

Unless a named product owner approves a stricter replacement before rehearsal,
the MVP pilot uses these thresholds:

- ordinary API operations and application navigation: p95 below 2 seconds and
  p99 below 4 seconds at 50 concurrent users for a 10-minute steady-state run,
  after a 2-minute warm-up, with fewer than 1 per cent unexpected errors;
- bounded statistics, calendar and board reads: p95 below 2 seconds over at
  least 2,500 requests, 250 active users, 5,000 calendar occurrences and 2,500
  work packages in the authorised scope;
- accessibility automation: zero critical or serious axe findings in every
  named pilot page, followed by successful keyboard-only, visible-focus,
  200 per cent zoom and reduced-motion review;
- security tooling: zero unresolved critical or high findings. Medium findings
  require a recorded disposition and owner;
- recovery: no duplicate business records or workflow tasks, no lost committed
  data, reconciliation within 15 minutes of dependency recovery, and a verified
  PostgreSQL restore into a clean database within 30 minutes in the local pilot
  rehearsal; and
- browser support: the installed current stable Chrome, Edge and Firefox
  versions are recorded and all critical pilot journeys pass in each browser.

## Definition of Done for every feature

### Product and scope

- A Markdown specification exists before implementation and contains user
  outcomes, explicit non-goals, data ownership, permissions, error behaviour and
  measurable acceptance criteria.
- Representative terminology is used consistently. No retired domain language is
  introduced into application code, routes, schemas, tests or user-facing copy.
- A material or expensive-to-reverse decision has an accepted ADR.
- Security-sensitive work updates the relevant threat model before the feature is
  declared complete.
- The master plan, development story and operating documentation describe the
  implemented state without stale or aspirational claims.

### Architecture and data

- Domain rules remain independent of FastAPI, SQLAlchemy, React and Camunda.
- FastAPI routes are thin, application services own use cases, and repositories
  own persistence and scoped queries.
- PostgreSQL remains authoritative for business content, identity, permissions,
  analytics facts, calendar data, team membership and audit history.
- Camunda remains authoritative only for process position and user-task
  lifecycle. React never calls Camunda directly.
- Every schema change has an Alembic migration proven against an empty database
  and the previous supported revision. Upgrade, drift and rollback evidence is
  retained.
- Historical identities, organisation units, memberships, requests, events and
  work ownership are ended or superseded, never destructively removed when
  referenced.
- Concurrent mutations use row locks or an equivalent serialisation boundary,
  optimistic versions and one-winner tests.
- Outbox and reconciliation operations are idempotent and do not invent workflow
  state after partial failure.

### Security and privacy

- Authentication, CSRF, trusted-origin and active-account checks are enforced at
  the server boundary.
- Role, object, organisation scope and action authority are rechecked in the
  final database transaction, not inferred from navigation or client input.
- Direct identifiers, sibling units, ancestor units, stale grants and revoked
  memberships have explicit negative tests.
- Platform administration and aggregate analytics do not expose Customer request
  content or service products.
- Calendar privacy, feedback confidentiality and small-cohort analytics controls
  are tested at the query boundary.
- No password, token, session identifier, private calendar note, request body or
  product content appears in logs, analytics events or audit summaries.
- Audit evidence is append-only in application behaviour, HMAC-linked and covered
  by integrity verification tests. Production database grants remain a release
  gate until independently enforced.
- Dependency, secret, static-analysis and container scans have no unresolved high
  or critical finding.

### User experience and accessibility

- Each new workspace records a visual thesis, content plan and interaction thesis
  before component work starts.
- Operational surfaces use the existing graphite ISTARI hierarchy, one cyan
  action accent, restrained dividers and dense readable rows rather than a grid
  of decorative cards.
- Loading, empty, success, stale, conflict, permission-denied and recoverable error
  states are implemented.
- All inputs have visible labels, required state, help and associated error text.
  Submission errors receive deterministic focus.
- All functions are usable with keyboard only and at 200 per cent zoom.
- Charts provide an equivalent data table and textual summary. Calendar and board
  interactions provide non-drag, keyboard-operable controls.
- Colour is never the only state signal. Focus, contrast, reduced motion and live
  announcements meet WCAG 2.2 AA.
- Current Chrome, Edge and Firefox pass the agreed pilot journeys.

### Quality and operations

- Backend and frontend application code each retain at least 95 per cent line and
  branch coverage. Thresholds are not reduced and exclusions are not added merely
  to pass a gate.
- Behaviour tests cover happy paths, validation, permissions, stale state,
  concurrency, retries, recovery and data minimisation.
- Hand-written source files remain at or below 350 lines.
- Formatting, lint, typing, build, terminology, OpenAPI and BPMN validation pass.
- Ordinary API and page p95 response time is below two seconds at the agreed pilot
  load. Analytics, calendar and board query bounds are separately evidenced.
- Health, structured logs, metrics, alert conditions, backup and restore steps are
  documented without sensitive payloads.
- A Playwright journey and a visual review cover desktop and narrow-screen states.
- The feature has no unresolved blocker, undocumented manual repair or known data
  migration ambiguity.

## Phase definitions

### Phase 0: Rebaseline and authority

Done when:

- the current 72-account, fully staffed organisation baseline replaces stale
  sixteen-user and OSG-only statements;
- the expansion specification, management-grant ADR, analytics ADR, calendar ADR
  and updated threat models are accepted;
- every new permission and visibility scope is defined independently from role
  labels and organisation parentage;
- seeded management grants identify the JIOC, command, Ops and team managers used
  in tests; and
- the master plan links each requirement to one phase and one evidence source.

### Phase 1: Customer data quality and closure

Done when:

- Customers can save, resume, edit and delete only their own incomplete drafts;
- every displayed business field is mandatory at final submission, while
  incomplete drafts remain private and cannot start Camunda;
- required markers, accessible errors and matching Zod and Pydantic constraints
  are tested;
- every recorded routing, hold, resume, rework and release decision has the
  mandatory evidence defined by its action schema;
- a released product is visibly downloadable from both the Customer register and
  request detail through an authenticated no-store endpoint;
- feedback requires the agreed rating and comment fields, is accepted once only
  after successful dissemination and remains unavailable for cancelled or closed
  without delivery requests; and
- dashboard refresh, retry and duplicate submission cannot create duplicate
  workflow starts, feedback or dissemination records.

### Phase 2: Analyst clarification

Done when:

- an assigned Analyst can request additional information from `IN_PROGRESS` and
  `REWORK_REQUIRED` before product submission;
- the question, reason, response deadline, messages, actors and timestamps are
  stored as a structured, append-only clarification thread in PostgreSQL;
- the Customer sees the full authorised thread under `Needs your input` and can
  submit a mandatory response or withdraw;
- an answered clarification returns to the same team and Analyst without JIOC,
  command or Ops approval;
- tracking users see only the metadata state `Awaiting Customer information`;
- a versioned BPMN definition and live Camunda smoke prove request, response,
  recovery and repeated clarification loops; and
- existing process instances remain pinned to their original definition version.

### Phase 3: Management grants and analytics facts

Done when:

- management authority is represented by versioned grants for an exact unit and
  optional descendants, not by a proliferation of application roles;
- grants independently control statistics, roster, calendar, board and capacity
  actions;
- organisation closure data rejects cycles and supports bounded descendant scope;
- stage intervals and request facts are projected idempotently from authoritative
  request and audit events;
- direct, child, ancestor, sibling, expired and revoked grant tests prove exact
  scope; and
- analytics responses contain no request narrative, product, Customer identity or
  feedback comment.

### Phase 4: Scoped operational statistics

Done when:

- JIOC managers see JIOC and authorised descendants;
- command managers see only their command and descendants;
- Ops managers see only their Ops group and direct teams;
- team managers see only their team;
- Platform Administrators see whole-organisation aggregates and platform health
  without request content;
- traffic, WIP, age, due risk, throughput, stage duration, clarification, rework,
  feedback and child-unit comparisons are available for bounded date ranges;
- small feedback cohorts are suppressed and every chart has a table equivalent;
  and
- cross-branch API tests prove, for example, that NCGI-A Ops cannot retrieve JIOC,
  SYGOC, Nimbus or unrelated DIGOC statistics.

### Phase 5: Team workspace and roster lifecycle

Done when:

- every configured team has an authorised workspace with Overview, Board,
  Calendar, People, Planning and Activity navigation;
- a team manager can add an existing active Analyst to their exact team, end a
  membership and schedule a transfer using a mandatory reason;
- only Platform Administrators can create or deactivate global identities and
  change global roles;
- one person has at most one effective home team at an instant;
- active task, work-package, commitment and reservation dispositions are required
  before removal or transfer;
- historical memberships remain queryable and staffing state is recalculated; and
- a manager cannot alter a sibling, ancestor or unrelated team.

### Phase 6: Canonical workforce calendars

Done when:

- personal month, week and agenda views and a shared team calendar are present;
- all-day and timed events use validated IANA time zones;
- activities include availability, on-task, leave, training, duty, appointment
  and other;
- daily and weekly recurrence supports one-occurrence edit, future-series split
  and cancellation;
- privacy supports private, availability-only and team-detail projection;
- one canonical event projects into authorised team and ancestor views without
  copied absence records;
- authorised managers can create team events and personal commitments, while the
  subject can acknowledge or dispute a commitment with a reason;
- calendar events affect capacity deterministically and concurrent edits use
  versioned preview and commit; and
- external calendar synchronisation remains disabled until a separate connector
  security specification is accepted.

### Phase 7: Kanban and agile delivery

Done when:

- team and authorised descendant boards are projections of the service-request
  workflow and cannot bypass Camunda through drag-and-drop;
- board and table views cover awaiting assignment, ready, in progress, blocked,
  manager review, quality review, rework, on hold and recently completed work;
- filters, saved views, WIP limits and keyset pagination are implemented;
- teams can maintain a backlog of versioned work packages with owner,
  contributors, estimate, remaining effort, due date, priority, dependencies,
  blockers, acceptance criteria and immutable activity;
- package planning checks calendar-backed capacity before reservation;
- reassignment, contributor changes and handover preserve history and release
  obsolete reservations; and
- optional time-boxed iterations have goals, committed packages and completion
  evidence without replacing the continuous service-request flow.

### Phase 8: Assurance and pilot

Done when:

- every earlier phase passes its own definition and the programme evidence ledger
  contains current commands, results and artefacts;
- migration from the previous local schema and a backup restore are rehearsed;
- security, privacy, accessibility, browser and performance matrices pass with no
  unresolved severe finding;
- the complete Customer, Analyst, Manager, QC, statistics, calendar and board
  journeys pass in Playwright against PostgreSQL and Camunda;
- named product, security, operational and user-acceptance owners sign off; and
- no checklist item is marked complete from intention, partial implementation or
  a narrower test than the requirement.

## Programme evidence ledger

Each phase records:

| Evidence | Required record |
| --- | --- |
| Specification | File and accepted revision |
| Decision | ADR and status |
| Threat model | Updated file and reviewed abuse cases |
| Migration | Empty, previous-version, drift and rollback commands |
| Backend | Test count, line and branch coverage |
| Frontend | Test count, line and branch coverage |
| Workflow | BPMN validation, contract test and live smoke |
| Security | Static, dependency, secret and container scan results |
| Accessibility | Automated and manual keyboard evidence |
| Performance | Scenario, dataset, load and percentile results |
| Recovery | Outage, retry, reconciliation and restore results |
| User journey | Playwright artefact and visual-review record |
| Git | Branch, commit, remote and pull-request state |
