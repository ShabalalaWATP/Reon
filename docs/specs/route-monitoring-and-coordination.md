# Route monitoring and coordination

## Outcome

Routing users can distinguish work requiring a decision from requests they have
already passed onwards. A user in any unit on the immutable selected route can
monitor the request, understand its age and current owner, and review its
tamper-evident journey without regaining action authority.

## Monitoring register

- `My actions` contains only personal or shared-unit work requiring action.
- `Request tracking` contains requests whose immutable selected route includes
  one of the user's exact organisation memberships.
- The register shows reference, title, status, current owner, age, required date
  and selected route.
- Users can filter by reference or title, status, current owner, route
  destination and minimum age.
- Detail shows the original request and a paginated chronological event history.
- Membership of a parent or sibling unit does not imply visibility.

## Coordination

- The Customer, the current owner and users in units on the selected route may
  create an append-only coordination message addressed either to the Customer
  or the current owner.
- Messages do not change request state, assignment or workflow deadlines.
- Every message records its author, audience and timestamp and appends a
  tamper-evident request event. Notifications contain no message text.
- A route user may request return to an earlier unit on the selected route.
- A return request is not a transfer. It records the named upstream destination
  and reason for the current owner and every authorised route participant.
- The current owner fulfils it through the existing explicit return controls.
  Requests can travel back through NCGI-A Ops and DIGOC to JIOC without allowing
  a previous handler to seize or silently mutate live work.
- Nobody who merely monitored or previously routed a request may seize it.

## Acceptance criteria

1. JIOC, DIGOC and NCGI-A Ops can each monitor a request after routing it onward.
2. A user outside the selected route receives the same non-disclosing not-found
   response for list and detail access.
3. Filters compose and cursor pagination retains the selected filters.
4. Age is never negative and is calculated from submission creation time.
5. The complete authorised event trail includes workflow actions, transfers,
   return requests and responses, and Customer interactions.
6. Customer questions and owner questions are visible only to authorised
   participants and never copied into notification payloads or telemetry.
7. A return request does not alter ownership; only existing authorised workflow
   return actions can do that.
8. Every return action remains subject to the workflow's ownership, stage and
   optimistic-concurrency checks.
