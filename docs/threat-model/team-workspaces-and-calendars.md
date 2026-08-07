# Team Workspaces and Calendars Threat Model

## Scope and assets

This model covers team workspace access, membership lifecycle, calendar events,
commitments, work packages, saved views, capacity reservations and workflow board
projections. Protected assets include private calendar text, staffing history,
individual availability, workload, package notes and exact team boundaries.

## Trust boundaries

```text
Team browser -> React team workspace -> FastAPI action policy
                                    -> PostgreSQL membership and grants
                                    -> calendar, packages and reservations
                                    -> workflow-derived request projection

Only named workflow commands cross the existing outbox boundary to Camunda.
```

## Threats and controls

| Threat | Control |
| --- | --- |
| Team Manager alters another roster | Require an active exact-team roster grant in the locked mutation transaction |
| Manager creates or promotes a global identity | Team roster commands accept existing active Analysts only; global identity and role stay administrator-only |
| Concurrent transfers create two home teams | Exclusion constraint or serialised effective-range check plus one-winner concurrency tests |
| Member with active work is removed | Require explicit reassignment, handover or cancellation for tasks, packages, commitments and reservations |
| Historical attribution disappears | End effective membership; never hard-delete a referenced identity or membership |
| Private event text appears in team view | Redact at repository projection before schema construction; privacy matrix tests every view and role |
| Recurrence expansion exhausts resources | Restrict recurrence forms and occurrence window; limit range and result count |
| Daylight-saving conversion moves commitments | Store IANA zone and local intent; test gaps, overlaps, all-day boundaries and zone changes |
| Manager commitment impersonates consent | Record creator separately and require subject acknowledgement or reasoned dispute |
| Stale calendar preview overwrites work | Bind commit token to event, membership, reservation and version snapshot; return conflict on drift |
| Board drag skips workflow steps | Map source/target to a named application command and recheck task, assignment, state and version server-side |
| Package link changes request state | Keep package aggregate and request commands separate; link is reference-only |
| Large package history exhausts database connections | Bound package pages to 1–100 records and bulk-load contributors, dependencies, activity and reservations through a dedicated read projection |
| Cross-team saved view leaks identifiers | Scope filters and returned rows on every execution, not only view creation |
| Capacity reports expose private reasons | Use availability and duration only; omit event title, notes and dispute text |
| Notes or calendar text reaches logs | Structured metadata logging with sensitive-field redaction and regression tests |

## Required evidence

- Exact, sibling, ancestor, descendant, revoked and expired workspace-access tests.
- Membership add, end and scheduled-transfer tests with active-work disposition
  and concurrent changes.
- Calendar privacy tests across personal, exact-team Manager, team member,
  Platform Administrator and unrelated users. Organisational ancestors receive
  aggregate statistics only.
- Recurrence and time-zone property tests, including DST gaps and overlaps.
- Commitment acknowledgement, dispute, stale-preview and reservation tests.
- Board invalid-transition, assignment, stale-state and Camunda-outage tests.
- Package ownership, dependency-cycle, WIP and reservation consistency tests.
- Keyboard alternatives for board and calendar, 200 per cent zoom and reduced
  motion review.

## Residual risks and gates

Availability and workload metadata remain sensitive even when notes are hidden.
The pilot needs an agreed retention period, privacy notice and support procedure.
External calendar synchronisation, email notifications and arbitrary exports are
blocked until separately threat-modelled and approved.
