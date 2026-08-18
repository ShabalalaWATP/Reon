# Team Operations Workspace

Status: implemented current workspace contract. Last reviewed 18 August 2026.

## Purpose

Turn each authorised organisation workspace into a useful daily operating surface.
Delivery teams need a coherent view of allocation, execution, review, availability
and customer clarifications. Routing units need a decision queue, bottleneck view
and recent activity. The workspace must not duplicate Camunda, create a second
workflow or expose sibling and parent data.

## Product principles

- The overview answers what needs attention now. Deeper statistics remain on the
  Statistics page.
- Camunda remains authoritative for request position. Board gestures never bypass
  a named human workflow action.
- Work packages provide independently planned delivery work and may use audited
  board transitions.
- The server returns exact, scoped totals. A paginated page must never masquerade
  as the complete contents of a Kanban column.
- Availability and capacity support human allocation. They do not rank people or
  make assignments automatically.
- Delivery and routing workspaces share visual language but have different tools.

## Delivery-team home

The overview must show, in priority order:

1. overdue and due-soon work;
2. work awaiting assignment;
3. blocked work and customer clarification waits;
4. work awaiting Team Manager review;
5. upcoming leave, training and ticket commitments;
6. current people and workload; and
7. recent team activity.

Every attention signal links to the correctly filtered Board, Calendar or
Activity view. Managers and Analysts receive the same factual team
picture, with controls still governed by returned capabilities.

## Delivery board

The delivery view separates two different operating concepts. The always-visible
`Service request board` is a read-only projection of the Customer request
workflow. Its default active flow is Awaiting assignment, In progress, Blocked
and Manager review. Quality review, Rework and On hold form an expandable
exception and downstream section. Completed and Cancelled form an expandable
archive. Each service-request lane includes a short plain-English explanation of
the human action or wait state represented by that column.

The separately labelled `Work package Kanban` contains internal team-planning
cards only. It is collapsed by default and can be expanded or collapsed with a
keyboard-operable control. Its active flow is Backlog, Ready, In progress and
Blocked, with Completed and Cancelled in its own expandable archive. Work-package
moves remain reasoned and audited; they never change the Customer request stage.
When expanded, it presents a prominent `Create internal card` action in the
Kanban itself. A current Analyst creates a card owned by themselves and can move
cards they own or contribute to; a Team Manager retains team-planning authority.

The API returns aggregate column totals for the complete filtered result as well
as a bounded cursor page. Totals apply the same search, type, priority, owner and
due-date predicates and are not calculated from the current page.

The board provides:

- built-in views for Needs assignment, Overdue, Due this week, Blocked, Manager
  review and My work;
- personal saved views;
- a compact filter drawer and board/table presentation;
- visible WIP limits and breaches;
- an accessible work-item inspector;
- a focused Create internal card action inside the Work package Kanban rather
  than a permanently expanded form or a Manager-oriented global command;
- keyboard-accessible status selection for work packages;
- explicit links to named request workflow actions;
- due risk, age in state, owner, contributors, blocker, dependency, checklist and
  reservation context where those facts exist.

### Concurrent planning changes

- Active capacity reservations for one person use half-open time windows and
  must never overlap. PostgreSQL enforces the invariant with a partial GiST
  exclusion constraint, including when requests arrive in separate processes.
- A constraint conflict returns the stable board-planning conflict response and
  rolls back the losing reservation, its activity record and package revision.
- WIP admission, WIP configuration and dependency-graph changes serialise on
  the exact team planning aggregate before counting a lane or validating the
  complete graph. Competing changes therefore observe the committed winner and
  cannot jointly exceed a WIP limit or introduce a dependency cycle.

## Work-item inspector

The inspector is shared by board cards and table rows. It shows the authoritative
reference, status, ownership, due date, related request, planning context and
permitted actions. Work-package details include description, contributors,
acceptance criteria, blockers, dependencies, checklist progress, reservations and
activity. Request details are loaded only through the existing authorised request
endpoint and retain its object-level controls. A current exact-team Manager may
read the assigned team's active and terminal requests so the Board history is
operationally useful. This does not grant parent, sibling or unrelated-team
access.

## Capacity, calendar and skills

The workspace combines current membership, active work count, calendar
availability and protected reservations. Every member retains self-service leave,
training and other personal events. Managers retain exact-team commitments.

Profiles expose up to twelve optional, normalised, unique operational skill labels
to current team members and exact-team Managers. Account holders maintain their
own labels. Skills assist allocation and are not endorsements, scores or
performance measures.

## Clarification and review

Requests in Customer information required form the team clarification queue.
Their cards and home signals distinguish waiting for a customer from an internal
package blocker. New authorised responses continue to arrive through existing
notifications and request history.

Lead review forms the Manager review queue. Quality review and release remain
downstream, visible as read-only progress to the delivery team.

## Routing-unit home

Routing units do not receive a delivery Kanban. Their overview shows:

- unclaimed and personally claimed work;
- information-required work;
- oldest wait and due-risk signals;
- stage distribution;
- upcoming unit calendar events;
- links to the embedded work queue and scoped statistics.

Managers and Members still claim and complete their own routing decisions.
Manager position does not add allocation or approval.

## Internal work packages and supporting tools

The collapsible Work Package board is the team-owned space for scratch tasks,
blockers, dependencies and near-term coordination. It remains separate from the
workflow-derived Service Request board. Any capacity forecast is advisory and
never assigns work or advances Camunda.

The workspace may export content-minimal team briefs only after the existing
statistics/export policy confirms that the actor may see the selected scope.
External calendar synchronisation remains out of scope until separately approved.

## Accessibility and performance

- All drawers are dialogs with a labelled heading, close control, Escape support,
  focus containment and focus return.
- Every board move has a non-drag keyboard path.
- Status is not conveyed by colour alone.
- Board totals use bounded aggregate queries and ordinary pages target p95 below
  two seconds at pilot load.
- Reduced motion is respected.

## Acceptance criteria

- A Manager can identify assignment, due-risk, blocked, clarification and review
  work from the overview without opening Statistics.
- An Analyst can open `My assigned actions` and inspect complete authorised context.
- Column totals remain correct when more rows exist than the returned page.
- Terminal columns are collapsed by default and remain discoverable.
- The Service request board and Work package Kanban are visually and
  semantically separate, and work packages are collapsed by default.
- Every service-request lane explains the workflow meaning beneath its title.
- A current Analyst can create an internal card from the expanded Work package
  Kanban, with themselves fixed as owner, then move cards they own or contribute
  to through the planning lanes.
- A request card cannot be moved through a work-package command.
- A current exact-team Manager can inspect a terminal request assigned to that
  team, while a Manager in another team receives no existence signal.
- A routing member sees a decision dashboard and no delivery Kanban.
- A current team member can see bounded self-declared skill labels, while users
  outside that workspace cannot obtain them.
- Parent, sibling, revoked and expired users cannot obtain workspace totals,
  inspector detail, capacity or collaboration records.
- Frontend and backend line and branch coverage remain at least 95 per cent.
