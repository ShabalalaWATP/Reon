# Operator orientation and service timing

Status: implemented
Owner: Service operations
Last reviewed: 8 August 2026

## Purpose

Improve day-to-day orientation without changing the human-led workflow. Routing
users must understand the selected path and find an authorised destination at
scale. Every user must be able to identify their active workspace and signed-in
identity. Customers and staff must see factual age, waiting and required-date
information without an automated priority or routing judgement.

## User stories

### OST-01: Search the next authorised routing step

As a Routing User, I need to search the valid immediate children of the current
route by name or stable code so that a large set remains practical to use.

Acceptance criteria:

1. The API returns the selected root-to-current-stage path and only valid direct
   children of its final unit.
2. Search is literal, case-insensitive, trimmed and bounded to 120 characters.
3. Search never ranks, recommends, preselects or disables a valid destination.
4. Clearing search restores the complete server-authorised set.
5. The selected route and destination are available to keyboard and screen-reader
   users before submission.

### OST-02: Maintain shell orientation

As a signed-in user, I need one unmistakable active navigation state and a useful
account menu so that I know where I am and which authority I am using.

Acceptance criteria:

1. Exactly one primary navigation item is marked current, including request detail
   and new-request routes.
2. Hover and keyboard focus remain visually distinct from the active state.
3. The account menu identifies display name, account ID, role, scope and session
   expiry, and contains the sign-out action.
4. The menu closes on Escape, outside interaction and route change.
5. Status colours retain readable text and do not communicate by colour alone.

### OST-03: Understand elapsed service time

As a Customer or service operator, I need factual elapsed and required-date
indicators so that I can understand progress without an inferred priority.

Acceptance criteria:

1. Open requests show age from submission and time since the latest recorded
   update.
2. Work queues show time waiting in the current task from its creation timestamp.
3. Required dates state whether the request is due today, due in a number of
   calendar days, or past its required date.
4. Timing labels use stored timestamps and the viewing device clock. They do not
   change priority, routing, ownership, notifications or Camunda variables.
5. Completed or closed states are not described as currently waiting.

## Security and accessibility constraints

- Routing path metadata is returned only after existing work-item visibility and
  stage checks pass.
- The path contains organisation identifiers, display names, stable codes and
  kinds only. It contains no request narrative or candidate-group identifiers.
- Destination validation remains server-side and is repeated when the human
  outcome is completed.
- Timing calculations are presentation-only. The backend remains authoritative
  for stored timestamps and workflow state.
- Search and account controls have programmatic labels, live result text and
  visible focus indicators. Reduced motion preferences remain respected.

## Verification

- Backend repository and API tests prove pinned and legacy path construction,
  direct-child options and concealment for unauthorised or invalid-stage access.
- Frontend tests cover route filtering, clearing, selected-route summaries,
  single active navigation, account-menu keyboard behaviour and timing boundaries.
- Browser checks cover desktop and narrow layouts, keyboard focus and automated
  accessibility rules.
- The target PostgreSQL and Camunda rehearsal proves a non-default selectable
  route and controlled dependency recovery separately from unit tests.
