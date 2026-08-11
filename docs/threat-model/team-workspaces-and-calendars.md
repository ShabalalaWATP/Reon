# Team Workspaces and Calendars Threat Model

## Scope and assets

This model covers team workspace access, membership lifecycle, calendar events,
commitments, work packages, saved views, capacity reservations and workflow board
projections. It also covers package templates, checklist instances, blockers,
dependencies, iterations, handover previews and versioned capacity scenarios in
the planning cockpit. Protected assets include private calendar text, staffing
history, individual availability, workload, package notes and exact team
boundaries. Self-declared operational skill labels are team-visible profile data.
The model also covers narrow colleague-profile reads and Manager-sent task
hasteners stored in request history.

## Trust boundaries

```text
Team browser -> React team workspace -> FastAPI action policy
                                    -> PostgreSQL membership and grants
                                    -> calendar, packages and reservations
                                    -> planning scenarios and projections
                                    -> workflow-derived request projection

Only named workflow commands cross the existing outbox boundary to Camunda.
```

## Threats and controls

| Threat | Control |
| --- | --- |
| Member uses a stale or misconfigured roster grant | Require both a current exact-unit `MANAGER` membership and the active exact-unit roster grant at the FastAPI use-case boundary; React suppression is usability only |
| A broad role label conceals Manager authority from the account holder | Present the representative role and authoritative effective workspace position together in the account menu and separately in the profile; continue to authorise only from the server-side membership and grant |
| A workspace user enumerates accounts or reads private profile fields | Require exact-workspace read access and exact-team membership history for the subject; return the same not-found result for absent and inaccessible records; expose only the bounded colleague contract and exclude service number and free-form personal notes |
| Team Manager alters another roster | Require a current exact-team Manager position and active exact-team roster grant in the mutation transaction; restrict team controls to Member records |
| Manager creates or promotes a global identity | Team roster commands accept existing active Analysts only; global identity and role stay administrator-only |
| Concurrent transfers create two home teams | Exclusion constraint or serialised effective-range check plus one-winner concurrency tests |
| Member with active work is removed | Require explicit reassignment, handover or cancellation for tasks, packages, commitments and reservations |
| Historical attribution disappears | End effective membership; never hard-delete a referenced identity or membership |
| Private event text appears in team view | Redact at repository projection before schema construction; privacy matrix tests every view and role |
| A user unintentionally hides a routine personal event or misunderstands a technical visibility option | Default new personal activity to exact-unit detail, expose one unchecked plain-language `Private appointment` choice and reject availability-only personal creation at the server boundary; preserve existing records without silently changing their audience |
| A team-visible personal event exposes detail beyond the intended colleagues | Derive shared calendar projections only from current exact-unit membership; ancestors and siblings receive aggregate statistics rather than calendar records |
| A personal-calendar account without a workspace gains team visibility | Allow the account to read and change only events where it is the authenticated subject; project events into team calendars only through current exact-unit membership resolved at read time |
| Recurrence expansion exhausts resources | Restrict recurrence forms and occurrence window; limit range and result count |
| Daylight-saving conversion moves commitments | Store IANA zone and local intent; test gaps, overlaps, all-day boundaries and zone changes |
| Manager commitment impersonates consent | Record creator separately and require subject acknowledgement or reasoned dispute |
| Stale calendar preview overwrites work | Bind commit token to event, membership, reservation and version snapshot; return conflict on drift |
| Board drag skips workflow steps | Map source/target to a named application command and recheck task, assignment, state and version server-side |
| A Manager sends a hastener to an unassigned or cross-team Analyst | Require a current exact-team Manager position, exact assigned-delivery-team ownership and active production state; derive active Lead and Contributor recipients on the server and validate every named recipient against that set |
| A hastener becomes an untracked workflow shortcut | Append it to tamper-evident request history with unchanged prior and next status; keep ownership and assignment unchanged and send no Camunda command |
| A reminder notification exposes request narrative to the wrong person | Project only to the resolved assigned Delivery Specialists through exact-team recipient rules; keep the subject content-minimal and link back to the authorised board endpoint where object access is rechecked |
| Internal reminder text leaks through Customer request history | Filter `task_hastener` events from the Requester read model on the server; retain them for exact-team Managers and active assigned Analysts only |
| A hostile reminder message manipulates rendering or logs | Normalise and bound the mandatory message, reject control and bidirectional formatting characters, escape it at render time and keep structured logs content-free |
| Package link changes request state | Keep package aggregate and request commands separate; link is reference-only |
| Large package history exhausts database connections | Bound package pages to 1–100 records and bulk-load contributors, dependencies, activity and reservations through a dedicated read projection |
| Cross-team saved view leaks identifiers | Scope filters and returned rows on every execution, not only view creation |
| Aggregate board totals reveal hidden work | Apply the same exact-team authorisation and filters before every aggregate query; never calculate a broader total and redact it in React |
| Inspector loads an inaccessible request or package | Reuse the authoritative object-level detail endpoint; allow terminal request history only for a current Manager membership in the exact assigned team; fail closed for parent, sibling, unrelated, expired and revoked access without confirming that an identifier exists |
| A compact board hides a workflow state | Keep exception, downstream and terminal state groups discoverable, include their scoped totals and provide an equivalent table view |
| Team home combines data into a broader side channel | Authorise each source independently, use exact-team or authorised descendant scope and render no partial protected data after a failed required query |
| Capacity reports expose private reasons | Use availability and duration only; omit event title, notes and dispute text |
| A capacity estimate automatically assigns work | Label estimates and source freshness; require a named Manager-led assignment or handover command and never move a Camunda task from a scenario |
| A stale planning scenario overwrites commitments | Bind preview and commit to membership, calendar, work, package and reservation versions; return a conflict when any source drifts |
| Reassignment loses accountable handover | Preview affected tasks, packages, commitments and reservations, then record the Manager, reason, previous owner and accepted target in one transaction |
| A dependency cycle makes planning unusable | Reject cycles in the package dependency graph and bound traversal depth and result size |
| Blocker or checklist text leaks across teams | Apply exact-team ownership and grant policy on list, detail, notification and saved-view execution |
| Iteration completion becomes an individual ranking | Report factual team commitment and completion only; do not create Analyst league tables, surveillance scores or inferred performance measures |
| Planning notification exposes private calendar detail | Publish content-minimal assignment, blocker, due-risk, iteration and dispute events without event title, notes or private reasons |
| Skill labels become an allocation score or leak outside the team | Bound and normalise self-declared labels, return them only through the authorised exact-team people projection and prohibit proficiency scores, inferred ranking and automated assignment |
| Notes or calendar text reaches logs | Structured metadata logging with sensitive-field redaction and regression tests |

## Required evidence

- Exact, sibling, ancestor, descendant, revoked and expired workspace-access tests.
- Deliberately misconfigured Member-grant tests proving that eligible-person,
  add, transfer and end-membership use cases fail closed independently of React.
- Membership add, end and scheduled-transfer tests with active-work disposition
  and concurrent changes.
- Calendar privacy tests across personal, exact-team Manager, team member,
  Platform Administrator and unrelated users. Organisational ancestors receive
  aggregate statistics only.
- Creation-policy tests proving team-detail is the client default, private is an
  explicit user choice and availability-only personal creation is rejected.
- Recurrence and time-zone property tests, including DST gaps and overlaps.
- Commitment acknowledgement, dispute, stale-preview and reservation tests.
- Board invalid-transition, assignment, stale-state and Camunda-outage tests.
- Board aggregate tests proving totals are independent of pagination and remain
  exact-team scoped under every supported filter.
- Inspector tests for direct identifiers, cross-team identifiers, revoked access,
  terminal exact-team Manager history, keyboard focus containment and
  request/work-package command separation.
- Package ownership, dependency-cycle, WIP and reservation consistency tests.
- Template/checklist ownership, blocker ageing and iteration-boundary tests.
- Capacity-scenario drift across leave, recurrence, transfer, active work,
  reservations, commitments and reassignment.
- Manager-led handover audit tests and proof that no scenario, board gesture or
  planning notification mutates Camunda directly.
- Planning-notification recipient and content-minimisation tests.
- Profile skill validation plus exact-team, sibling, revoked and expired people-
  projection tests.
- Colleague-profile exact-team, privacy, missing-record and sibling-team tests,
  plus keyboard navigation back to the same People register.
- Hastener tests for any current exact-team Manager, one and all active assigned
  Analysts, unassigned and cross-team denial, inactive production denial,
  immutable history, Customer-history exclusion, notification recipients and
  unchanged workflow state.
- Fixed 5,000-occurrence and 2,500-package performance evidence with visible
  source freshness.
- Keyboard alternatives for board and calendar, 200 per cent zoom and reduced
  motion review, extended to every planning-cockpit command.

## Residual risks and gates

Availability and workload metadata remain sensitive even when notes are hidden.
The pilot needs an agreed retention period, privacy notice and support procedure.
External calendar synchronisation, email notifications and arbitrary exports are
blocked until separately threat-modelled and approved.
Capacity scenarios can still influence human decisions. Representative-user
acceptance must confirm that estimates are understood as advisory and do not
become an informal performance-ranking mechanism.
