# Action deep links and workspace navigation

## Problem

The personal action register projects every request action to a Customer-only
`/requests/{id}` route. Staff roles fail that route's role check and are sent to
their landing overview, losing the selected request. The staff queue also has no
request-addressable entry point and defaults to its first visible work item.

The navigation labels **My work**, **Work queue** and **Workspace** do not explain
the distinction between personal or claimable actions, workflow decisions and
unit collaboration.

## Outcome

An authorised user can open an action and arrive at the exact current work item.
The link must never expose request content or silently substitute a different
item when the requested work is no longer available. Navigation must name the
role queue and organisation workspace clearly.

## User stories

### Routing user opens an available action

As a JIOC Routing User, I want an action link to open the matching JIOC queue
item so that I can claim and route the intended request without finding it again.

### Assigned user returns to their action

As the person who claimed a workflow task, I want the action register to identify
the work as assigned to me and reopen that exact task.

### Another unit member sees accurate availability

As another member of the same unit, I must not see a task as available to me once
somebody else has claimed it.

### User follows an ended or inaccessible action

As an authorised user, I want a clear unavailable message when a linked task has
ended or my access changed, rather than being shown an unrelated queue item.

### User understands the navigation

As a member of JIOC, I want to see **My assigned actions**,
**JIOC routing queue** and **JIOC workspace** so that I can distinguish an action
inbox, routing decisions and unit collaboration.

## Functional requirements

1. Customer actions continue to link to their authorised request page.
2. Staff workflow actions link to the role queue with an opaque request UUID in
   the `requestId` query parameter.
3. JIOC, command, Ops, Team Manager, Team Analyst and QC actions use their own
   queue route.
4. The work-list API accepts an optional `requestId` filter and applies it inside
   the existing actor-scoped query.
5. The queue uses a distinct query-cache key for a request-addressed view.
6. A request-addressed queue containing no visible item displays an explicit
   unavailable state and a link to the unfiltered role queue.
7. Action responses distinguish `PERSONAL` actions from `SHARED` actions.
8. An unclaimed role candidate is `SHARED`. A claimed task is reprojected only
   to its assignee and is `PERSONAL`.
9. The action register displays **Assigned to you** or
   **Available to &lt;current unit&gt;** without treating availability as assignment.
10. Staff navigation uses **My assigned actions**, a purpose-specific routing or
    delivery queue label and the configured organisation name followed by
    **workspace**.

## Security requirements

- `requestId` is a selector, never proof of access.
- FastAPI applies existing role, route-membership, task-state and assignee checks
  before returning a work item.
- An inaccessible, completed or differently assigned item is indistinguishable
  from a missing item in the API result.
- Deep links remain relative application URLs and pass existing link validation.
- The action register contains only the existing content-minimised projection.
- No automatic claim, route or workflow decision occurs when a link is opened.

## Acceptance criteria

- Opening a JIOC action for request A shows request A in the JIOC queue.
- It never shows request B as a fallback.
- Claimed work disappears from another eligible JIOC user's action register.
- The assignee sees the same action marked **Assigned to you**.
- All supported staff roles receive the correct queue deep link.
- The sidebar distinguishes actions, queue and workspace using accessible link
  names and preserves active navigation styling.
- Backend and frontend line and branch coverage remain at least 95 per cent.
