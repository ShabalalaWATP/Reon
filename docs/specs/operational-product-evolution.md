# Operational Product Capabilities

## Status

Current capability contract. Last reviewed 10 August 2026. Operational,
security, infrastructure and production acceptance remain governed by the
current readiness register and release gates.

The proposed `structured-conversations-packages-and-contexts.md` specification
extends the package envelope, QC separation and dual-context rules. Until that
amendment is accepted and implemented, this document remains the authority for
current managed-product behaviour.

## Outcome

Give every authorised user a focused operational workspace, notify them when
their action is required, let Quality and Release Managers disseminate managed
files or approved product links through the Customer dashboard, and let the
organisation expand without hard-coded teams or unsafe workflow editing.

The human-led route is:

`Customer -> JIOC -> command -> Ops group -> delivery team -> Team Analyst ->
Team Manager -> Quality and Release Manager -> Customer`.

JIOC, command and Ops users route and track. They do not approve the product.
Camunda coordinates named human tasks and never chooses a route, priority,
assignee, approval or recipient.

## Scope

This contract covers:

1. role-specific action workspaces and personal inboxes;
2. an auditable in-application notification centre;
3. dashboard dissemination of managed PDF, Word and PowerPoint products or an
   approved external HTTPS product link;
4. versioned organisation, routing and bounded workflow configuration;
5. enhancements to the existing team board, calendar and planning workspace;
6. enhancements to existing organisation-scoped operational statistics; and
7. the migrations, security controls, evidence and operating procedures required
   to release those capabilities safely.

Production identity, hosting and infrastructure remain separate go-live gates.
Email, Teams and external calendar connectors may use the notification and
integration ports created here, but require a separate connector specification
and threat model before activation.

## Product principles

- Consequential actions remain explicit, attributable human decisions.
- PostgreSQL remains authoritative for product data, configuration, permissions,
  notifications, planning records, analytics facts and audit history.
- Camunda remains authoritative for process position and user-task lifecycle.
- Dashboard action items are projections of authoritative state, not a second
  task system.
- Submitted request data stays mandatory and versioned. Configuration cannot
  make an approved core submission field optional.
- Customers receive products only after an independent QC dissemination action.
- Product content, Customer identity and private calendar text never enter
  notifications, analytics facts or routine logs.
- Configuration is declarative and constrained. Administrators cannot upload
  scripts, expressions or arbitrary BPMN through the application.
- Historical records retain the organisation, workflow, form and product-release
  versions that governed them.

## Role-specific action workspace

Each staff account receives a `My actions` workspace. The server assembles action
items from current Camunda tasks and product-owned projections, then applies
role, assignment, object and organisation policy before returning them. The
Customer's equivalent action surface is `My requests`, where clarification,
released-product and feedback actions stay attached to the relevant request.

| Role | Action groups |
| --- | --- |
| JIOC Routing User | New submissions, claimed intake, held work and due-risk routing |
| Request Coordination User | Requests awaiting an Ops choice, held work and returns |
| Ops Routing User | Requests awaiting a team choice, staffing waits and returns |
| Team Manager | Team intake, assignment, due risk, Manager review and rework |
| Team Analyst | Assigned work, clarification replies, due risk and returned products |
| Quality and Release Manager | Quality review, returned products and release-ready work |
| Platform Administrator | Configuration, account and operational exceptions without request content |

The workspace provides:

- `Needs my action`, `Waiting`, `Due soon` and `Recently completed` sections;
- reference, safe title where authorised, current owner, required date, age and
  last change;
- bounded filters, saved views and configurable visible columns;
- direct links to the authorised record and its specific action;
- loading, empty, stale, conflict and permission-loss states; and
- keyboard-operable table and compact list views at desktop and narrow widths.

There is no bulk routing, approval, product release or closure. Bulk action is
limited to safe view operations such as marking notifications read.

## Notification centre

### Events

The notification centre records at least:

- request submitted or withdrawn;
- human task assigned, reassigned or returned;
- clarification requested, answered, overdue or withdrawn;
- required date approaching or passed;
- Manager review requested, approved or returned;
- QC review requested, approved or returned;
- product disseminated, replaced or withdrawn;
- Customer feedback requested or received;
- team membership or capacity commitment changed; and
- configuration awaiting review, activated, rejected or superseded.

### Behaviour

- Domain events create notifications through a transactional outbox.
- A stable event and recipient key makes creation idempotent.
- Recipient rules are server-owned and are evaluated again on every read.
- Notification text contains only the minimum metadata needed to identify the
  action. Clarification text, request narrative and product content are excluded.
- Each notification records unread, read, archived and action-completed state.
- Users can filter by state, event type and date and can mark one or many items
  read or archived.
- A notification deep link opens only after ordinary endpoint authorisation. A
  notification never grants access by itself.
- Revoked grants, ended memberships and disabled accounts remove live access
  immediately while retaining the audit record.
- The header count and active action page (`My requests` for Customers or
  `My actions` for staff) refresh without a full-page reload. A bounded polling
  fallback remains available if live updates fail.

Preferences cover in-application event groups and due-date reminder windows.
Safety-critical account and release notifications cannot be entirely disabled.
External delivery preferences remain dormant until an approved connector exists.

## Product dissemination

### Release package

An Analyst submits a versioned product release package. A package contains one to
ten artefacts. Each artefact is exactly one of:

1. a managed file in PDF (`.pdf`), Word (`.docx`) or PowerPoint (`.pptx`) format;
   or
2. an approved external HTTPS product link.

Legacy `.doc` and `.ppt`, macro-enabled Office formats, archives, executables and
embedded active content are rejected. The approved file list can become narrower
through configuration but not broader without a new security decision.

The Team Manager reviews the exact package version. QC reviews the same immutable
version and explicitly disseminates it to the originating Customer. Changing an
artefact after review creates a new package version and invalidates earlier
approval.

### Managed files

- PostgreSQL stores metadata, version, checksum, scan result, ownership,
  lifecycle and dissemination evidence. It does not store file bytes.
- An S3-compatible object store holds quarantine and released objects. Local
  development uses a local-compatible service; production selects an approved
  managed equivalent.
- Uploads use a short-lived, single-purpose upload intent with server-enforced
  object key, size and expected media type.
- The scanner checks size, extension, media type, magic bytes, archive structure,
  encryption state, active content and malware before promotion.
- A failed, unknown or timed-out scan cannot be reviewed or disseminated.
- Released objects are private and cannot be addressed through a public bucket
  URL.
- The application download endpoint rechecks active Customer ownership,
  dissemination state and artefact lifecycle, then streams or redirects using a
  short-lived object-store grant.
- Responses use `no-store`, `nosniff`, safe attachment filenames and an explicit
  download disposition. Every successful and denied attempt is audited without
  recording product content.

### Approved external links

- Links must be absolute HTTPS URLs on an administrator-managed allow-list.
- User information, embedded credentials, fragments, non-standard schemes,
  loopback addresses and literal private-network hosts are rejected.
- Mist Service stores and displays the normalised destination domain, product
  label, optional expiry and the approving actor.
- The backend never fetches or previews the destination, avoiding an SSRF and
  content-ingestion boundary.
- The Customer follows an authenticated application redirect that rechecks the
  release and recipient, audits the access, and opens the destination with safe
  browser isolation.
- QC must attest that the intended Customer can access the destination and that
  its handling is appropriate. Expired, replaced or withdrawn links are disabled.

### Customer dashboard

After dissemination, `My requests` and request detail show `Product available`.
The release panel displays every artefact with type, version, released time,
releasing QC Manager and either `Download` or `Open product`. Before release,
other Customers, routing users, unrelated teams and Platform Administrators
cannot retrieve the artefact or destination.

## Configurable organisation and workflow

### Organisation configuration

Platform configuration uses immutable versions with `Draft`, `Validated`,
`Awaiting approval`, `Active`, `Superseded` and `Rejected` states. A version may:

- create a command, Ops group or delivery team under a valid parent;
- rename a unit while retaining its stable identifier and name history;
- move a unit to a valid parent from an agreed effective time;
- retire a unit from new routing without deleting history;
- configure routing-pool and delivery candidate-group mappings;
- maintain team staffing requirements and routing availability; and
- assign management grants separately from routing membership.

Validation rejects cycles, skipped hierarchy levels, duplicate identifiers,
orphaned units, invalid candidate groups and an organisation with no complete
Customer-to-team route. An unstaffed team can remain selectable, but activation
must warn that work will wait at `Awaiting team staffing`.

High-impact configuration requires step-up authentication, a reason, preview and
approval by a different authorised configuration approver. Local fixtures
include `admin1` and `admin73` as separate synthetic Platform Administrators so
the evaluation can prove separation of duties.

The administrator interface presents the **Current configuration** and
**Proposed changes**, not internal draft/version terminology. Search by display
name, stable code or unit kind retains ancestor context; a keyboard breadcrumb
identifies the selected path; and create/move operations list only effective
parents of the immediately preceding kind. Immutable revisions, expected-revision
checks and request pinning remain API, persistence, audit and support controls.

### Workflow configuration

The application exposes bounded workflow templates rather than arbitrary BPMN
editing. An approved template version may define:

- the active request-form version and core-field catalogue;
- allowed service categories and preferred product types;
- the organisation root and permitted route depths;
- human task labels, due-date reminder rules and allowed human outcomes;
- approved product artefact types and link domains; and
- the vetted Camunda process-definition version to start.

Activation validates the complete template against a signed application schema
and a deployed, compatible BPMN definition. Configuration cannot add executable
code, bypass a human stage, make mandatory core fields optional, grant content
access or change an in-flight process.

New requests use the active configuration snapshot. Existing requests stay
pinned to their organisation, form, workflow and notification-policy versions.
A separate, explicitly designed migration is required if a future owner chooses
to move in-flight work.

Semantically unordered template fields are canonicalised before comparison.
Normalisation-only changes and unchanged existing staffing shortfalls must not be
presented as newly introduced change impact.

## Internal work-package enhancements

The existing canonical calendar, workflow-derived board and independent work
packages remain the foundation. The enhancement adds:

- one collapsible internal Work Package board combining backlog, due risk, WIP
  and near-term capacity without copying authoritative records;
- team-owned package templates and checklists;
- board swimlanes for owner, priority, service requests and internal package work;
- explicit blocker ageing and dependency warnings;
- iteration planning, commitment review and a factual completion summary;
- versioned capacity scenarios using memberships, calendar availability, active
  request work and package reservations;
- Manager-led reassignment and handover previews; and
- notifications for assignment, blockers, due risk, iteration changes and
  disputed commitments.

Capacity and workload signals advise people. They never assign Analysts, change
priority or move Camunda tasks automatically. Individual performance rankings,
surveillance scoring, payroll and HR leave approval remain out of scope.

## Statistics enhancements

Existing management grants and content-free analytics facts remain mandatory.
Enhancements add:

- current period versus previous period comparison;
- received, completed and active-work trends;
- stage bottleneck and ageing analysis;
- workload, calendar capacity and reservation trends at authorised team level;
- notification response and unresolved-action measures;
- managed download and external-link access counts without product content;
- product replacement, withdrawal and release-cycle measures;
- iteration commitment and completion summaries;
- deterministic demand and capacity projections labelled as estimates; and
- controlled aggregate CSV and accessible PDF exports with audit, cohort
  suppression and the same grant checks as the screen.

No chart identifies or ranks an Analyst. Platform Administrators retain
content-free whole-platform health only. Every chart uses the same tabular API
rows as its accessible table and textual summary.

## Data ownership and principal records

PostgreSQL owns action projections, notification records and preferences,
product-package and artefact metadata, scan and dissemination records, external
link policy, configuration versions and approvals, planning extensions,
analytics facts and append-only audit events.

The object store owns quarantined and released file bytes. Camunda owns process
position and human task state. React owns transient presentation state only.

All cross-boundary operations use outbox, idempotency and reconciliation. The
system exposes freshness or pending state instead of inventing success.

## Error and recovery behaviour

- A stale action or configuration version returns a conflict and safe refresh
  metadata.
- A Camunda outage leaves actions pending and notifications factual.
- An object-store or scanner outage leaves the artefact quarantined and blocks
  review and release.
- A removed file or expired external link remains in history but cannot be
  opened.
- Notification projection lag displays freshness and repairs idempotently.
- Analytics and planning projection lag is visible and cannot silently show a
  current timestamp.
- Permission failures do not reveal that an out-of-scope request, product,
  organisation unit or notification exists.

## Non-goals

- automatic triage, prioritisation, routing, assignment, approval or release;
- arbitrary BPMN, scripts, expressions or plug-ins uploaded by administrators;
- public object URLs or unauthenticated product links;
- unrestricted file types, public cloud shares or backend URL previewing;
- email, SMS, Teams or external calendar activation without a separate approved
  connector design;
- individual Analyst league tables or inferred performance scores;
- replacing Camunda task state with inbox, board or notification state; and
- production go-live without the separate identity, infrastructure and
  operational readiness gates.

## Acceptance outcomes

The capability is complete only when:

1. every representative role can complete its action journey (`My requests` for
   Customers and `My actions` for staff) and cannot see sibling, ancestor or
   unrelated action items;
2. every required event creates one correctly scoped notification and replay
   creates no duplicate;
3. a Customer can download released PDF, DOCX and PPTX artefacts or open an
   approved HTTPS product link from both dashboard and request detail;
4. malicious, mismatched, oversized, unscanned, unreleased, replaced and
   cross-Customer artefacts are denied;
5. an administrator can prepare and validate proposed changes, a separate
   approver can activate them, and a new request completes through its own
   Camunda groups;
6. in-flight requests continue under their pinned versions after a configuration
   activation;
7. planning enhancements preserve calendar, board, package and workflow truth
   under concurrency and handover;
8. every enhanced statistic passes exact-unit, descendant, sibling, revoked and
   small-cohort tests and contains no prohibited content;
9. keyboard, focus, zoom, narrow-width, reduced-motion, chart-table and supported
   browser evidence passes; and
10. coverage, migration, performance, recovery, security scanning, threat-model
    and stakeholder-acceptance gates pass without lowering existing thresholds.
