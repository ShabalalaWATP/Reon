# Service Operations Expansion

## Status

Proposed implementation baseline, 7 August 2026. This specification is governed
by `docs/PROGRAMME_DEFINITIONS_OF_DONE.md` and supersedes narrower exclusions in
the original MVP specification only for the capabilities defined here.

## Outcome

Extend ISTARI Service into a secure request-to-delivery workspace where:

- Customers submit complete structured requests, track them and receive the
  released product link in their dashboard;
- assigned Analysts can pause production to request and retain further
  information from the Customer;
- Customers provide a service rating and feedback after release;
- authorised managers see aggregate statistics for precisely their part of the
  organisation;
- every delivery team has a shared workspace, roster, calendar and workflow-led
  board; and
- team planning adds useful agile practices without replacing the human-led
  Camunda workflow.

JIOC, command and Ops levels route and track work. They do not approve the
finished product. The producing Analyst submits to their Team Manager, then the
Quality and Release Manager disseminates the approved product directly to the
Customer.

## Visual thesis

A calm graphite operational surface with compact scoped metrics, readable work
rows and one cyan accent for the current action. Statistics, calendars and boards
must feel like parts of the existing ISTARI shell, not separate generic dashboard
products.

## Content plan

1. Put the active organisation or personal scope, date range and filters first.
2. Put the primary operational view next: request register, statistics, board,
   calendar or people roster.
3. Put selected-record detail in a focused panel or page with one primary action.
4. Keep permission explanations, freshness, empty states and table alternatives
   next to the data they qualify.

## Interaction thesis

Use restrained, reduced-motion-safe transitions between list, board, calendar and
detail states. Preserve keyboard focus across filters and view changes. Every
drag action has an explicit keyboard-operable alternative, and every chart can be
switched to a data table.

## Terminology

| Use | Meaning |
| --- | --- |
| Customer | Person requesting and receiving a service product |
| Service request | The structured record of need |
| Product | The completed deliverable released to the Customer |
| JIOC routing | Initial intake, categorisation and command selection |
| Command routing | Selection of a direct Ops group |
| Ops routing | Selection of a direct delivery team |
| Team Manager | Allocates and checks team delivery work |
| Team Analyst | Produces the product and requests further information |
| Quality and Release Manager | Performs final quality review and dissemination |
| Management grant | A time-bounded authority over one organisation unit and
  optionally its descendants |
| Work package | A team-owned planning item that can support, but not replace, a
  service request workflow |

## Organisation and management scope

The canonical hierarchy remains `JIOC -> command -> Ops group -> delivery team`.
All configured branches in `docs/architecture/ORGANISATION_AND_ROUTING.md` are
first-class and selectable.

Statistics and workspace access are not inferred solely from a person's product
role. PostgreSQL stores explicit management grants. A grant identifies:

- the subject user;
- the root organisation unit;
- whether descendants are included;
- independent actions for statistics, roster, calendar, board and capacity;
- effective-from and optional effective-until times;
- granting actor, mandatory reason and optimistic version.

The local fixture grants are:

- `admin4`: JIOC statistics with descendants;
- `admin5`: separate descendant statistics grants for DIGOC, SYGOC and MYGOC;
- `admin6`: NCGI-A Ops, Aurora Ops, Vertex Ops, Nimbus Ops and Parallax Ops;
- `admin10`: Horizon Ops, Meridian Ops, Solstice Ops and Frontier Ops; and
- every active Team Manager: their exact team for statistics, roster, calendar,
  board and capacity.

These fixtures demonstrate scope and do not create a special universal Manager
role. A Platform Administrator can govern grants but does not gain request
content through administration or aggregate reporting.

## Customer request quality

### Drafts

A Customer can create, update, resume and delete their own draft. A draft is
private, has no Camunda instance and may be incomplete. Draft writes require an
expected version, so two tabs cannot silently overwrite one another.

### Final submission

Every displayed business field is mandatory at final submission:

- title;
- service category;
- description of the need;
- specific question to answer;
- desired outcome;
- background and known context;
- subject area or location;
- relevant period start and end;
- Customer urgency;
- activity, project or decision supported;
- required-by date;
- reason for the required date;
- preferred product type;
- success criteria;
- constraints or caveats;
- supporting information available; and
- sensitivity and handling instructions.

Client validation provides immediate help, but matching Pydantic validation is
authoritative. Blank, whitespace-only, invalid-date and over-limit values are
rejected. The first invalid field receives focus and a summary links to all
errors. A retry with the same idempotency key creates one request and one workflow
start.

Human decisions that change route, ownership, hold, return, rework, release or
closure require a bounded reason or decision note. The system never records an
unexplained transition.

### Tracking and release

`My requests` groups work into `Needs your input`, `In progress`, `Completed` and
`Closed`. Each row shows reference, title, current public status, current owner
label, required date and last change. A completed row includes an authenticated
`Download product` action. The request detail presents the same action and a
release receipt. Downloads use application-owned, `no-store` responses and are
available only to the originating active Customer after dissemination.

### Feedback

After dissemination, the Customer may submit feedback once. Both a 1 to 5 rating
and a bounded service comment are mandatory. The dashboard distinguishes
`Feedback requested` and `Feedback received`. Ratings are immutable to preserve
the operational record. Comments never appear in aggregate analytics or routine
logs. Cancelled and closed-without-delivery requests cannot receive feedback.

## Analyst clarification

The assigned Analyst may request further information while the request is
`IN_PROGRESS` or `REWORK_REQUIRED` and before submitting a new product version.
The command requires:

- a clear question;
- why the information is needed; and
- a response deadline.

PostgreSQL stores an append-only clarification thread with messages, actor IDs,
actor type, timestamps and status. There can be multiple sequential threads, but
only one unanswered thread per request. Customer replies and withdrawal are
idempotent and expected-version protected.

An open thread puts the request in `Awaiting Customer information`. The Customer
sees it under `Needs your input` with the authorised conversation. JIOC, command
and Ops trackers see only that state and timing metadata. The Team Manager sees
the thread. Unrelated users and Platform Administrators do not.

A reply resumes the same request with the same team and assigned Analyst. It does
not return for routing approval. Camunda completes the waiting Customer task and
creates the next Analyst task. Repeated clarification uses the same versioned
loop. Older workflow instances remain on their original process definition.

## Statistics

### Scope rules

- JIOC grant: the JIOC aggregate and authorised descendant comparisons.
- Command grant: that command and its descendants only.
- Ops grant: that Ops group and its direct teams only.
- Team grant: that exact team only.
- Platform Administrator: whole-platform aggregate and health only, with no
  request narrative, Customer identity, product or feedback comment.

An API request names one grant and a unit within its authority. The server derives
the permitted closure and never accepts client-supplied descendant IDs as proof.
Expired or revoked grants stop access immediately.

### Measures

For a bounded date range and stable time zone, the statistics workspace provides:

- received, routed, active, completed and closed request counts;
- current WIP by public stage;
- age bands and due-date risk;
- throughput over time;
- median and percentile stage duration;
- clarification count and response duration;
- return and rework rate;
- released-product and feedback completion rate;
- rating distribution and average only above the approved cohort threshold; and
- child-unit workload and throughput comparisons where the grant includes them.

All measures derive from content-free request facts and stage intervals.
Definitions, time range, time zone, last refresh and suppressed values are shown.
Every graph has a table and textual summary. Pagination and query bounds prevent
large hierarchy or date-range scans.

## Team workspace

Each delivery team has one workspace with these views:

- Overview: workload, due risk, staffing and near-term capacity;
- Board: workflow-derived service work and team work packages;
- Calendar: authorised shared availability and commitments;
- People: active and scheduled membership with workload context;
- Planning: backlog, estimates, dependencies and optional iterations; and
- Activity: immutable team-level metadata events.

Managers and Analysts have individual accounts. Team Analysts see their team and
own work. A Team Manager sees their exact team under the actions in their grant.
Cross-team visibility requires a separate explicit grant.

### Roster lifecycle

An authorised Team Manager can add an existing active Team Analyst, schedule a
transfer into their team or end a membership using a mandatory reason. They
cannot create identities, change global roles, deactivate accounts or alter
another team. Those remain Platform Administrator functions.

A person has at most one effective home-team membership at an instant. Ending or
transferring membership with active service tasks, packages, calendar
commitments or capacity reservations requires explicit reassignment, handover or
cancellation. History is retained with effective dates, actors and reasons.
Concurrent membership changes have one winner.

## Canonical calendar

Personal month, week and agenda views and an authorised shared-team view use one
canonical event model. Events support:

- all-day or timed periods with IANA time zones;
- availability, service work, leave, training, duty, appointment and other
  categories;
- daily or weekly recurrence;
- one-occurrence edits, future-series splits and cancellation;
- private, availability-only and team-detail visibility;
- team events and Manager-created personal commitments;
- subject acknowledgement or reasoned dispute; and
- optimistic versioning with preview before a multi-event or capacity change.

The same event projects into authorised personal, team and ancestor views. The
system does not create copied absence records. Private titles and notes are never
leaked through shared views, analytics, notifications or logs. External calendar
synchronisation is excluded until a separate connector threat model is approved.

Calendar periods contribute deterministically to day-level capacity. Conflicts
warn but do not silently rewrite dates. Time-zone and recurrence calculations are
stored and tested independently from rendering.

## Workflow-derived board and agile planning

The board shows service requests in columns derived from authoritative workflow
state: awaiting assignment, ready, in progress, blocked, Manager review, quality
review, rework, on hold and recently completed. Moving a request invokes the
specific authorised workflow command or is rejected. The UI never mutates a
column as an independent source of truth.

Board and table views support bounded filters, saved views, keyset pagination and
optional WIP limits. Keyboard users can perform every authorised action without
dragging.

Teams can create independent work packages for planning. A package has a title,
description, owner, contributors, estimate, remaining effort, due date, priority,
dependencies, blockers, acceptance criteria, version and immutable activity.
Packages may link to a service request but cannot change its route or state.

Capacity planning combines team membership, calendar availability, active
service work and package reservations. Reservation, reassignment and handover
are transactional and leave history. Optional iterations add a date range, goal,
committed packages and completion summary while continuous request flow remains
available.

Package list reads accept a page size from 1 to 100, defaulting to 50. Related
contributors, dependencies, activity and reservations are loaded as bulk read
projections so a populated team board does not create per-package database
round trips.

## Data ownership

- PostgreSQL: content, drafts, immutable revisions, clarification threads,
  products, feedback, management grants, organisation closure, analytics facts,
  memberships, events, packages, saved views, reservations and audit.
- Camunda: process position, user-task lifecycle and workflow definition version.
- React: transient view state only.

An outbox bridges durable product commands to Camunda. Projections are
idempotent, observable and repairable from authoritative product and workflow
events.

## Error and recovery behaviour

- Validation returns field-safe errors without echoing sensitive values.
- Permission denial does not reveal whether an out-of-scope object exists.
- Stale versions return a conflict and the current safe metadata needed to retry.
- Camunda outage leaves a visible pending command and never invents a completed
  state.
- Analytics, calendar and board projection delay shows freshness and degraded
  state instead of silently serving misleading data.
- Reconciliation can replay safely without duplicate workflow, message, product,
  feedback, fact, event or reservation rows.

## Non-goals

- automated triage, routing, prioritisation, matching or product generation;
- broad content search or unrestricted organisation reporting;
- chat, email, SMS or external calendar integration;
- arbitrary file uploads or analyst-provided download URLs;
- payroll, HR leave approval or a full enterprise project-management suite;
- replacing Camunda with board state; and
- production identity federation or production deployment.

## Acceptance

Every phase must satisfy its phase Definition of Done. In addition, the pilot
must prove:

1. complete draft, submission, tracking, release-link and feedback journeys;
2. repeated Analyst clarification returning to the same assignment;
3. positive and negative statistics scope for JIOC, command, Ops, team and
   Platform Administrator views;
4. exact-team roster changes with active-work and concurrent-transfer controls;
5. calendar privacy, recurrence, dispute and capacity behaviour;
6. workflow-derived board actions and independent package planning;
7. 95 per cent line and branch coverage for backend and frontend application
   code; and
8. security, accessibility, browser, performance, migration and recovery evidence
   with no unresolved severe finding.
