# Requester cancellation and personal profiles

## Outcome

Customers can cancel their own submitted request before it reaches a terminal
state, record why it is no longer required and see the request close
immediately. ISTARI durably terminates the corresponding Camunda process and
notifies the Customer and the staff already involved in its route. Every signed
in user can also maintain bounded personal profile information without changing
their role, access or governed organisation membership.

## Request cancellation acceptance criteria

- Only the Customer who submitted a request can cancel it.
- Cancellation is available for every non-terminal request state and is not
  available after completion, closure or an earlier cancellation.
- A reason of 10 to 1,000 characters and the current request version are
  mandatory. Blank, stale and repeated mutations fail closed.
- The PostgreSQL request projection changes to `CANCELLED` atomically with an
  append-only, hash-linked event and a durable Camunda cancellation intent.
- Open local workflow tasks, linked work packages and active capacity
  reservations are cancelled so queues and planning surfaces close immediately.
- A worker terminates an already-started Camunda process outside the database
  transaction. Cancellation before process start suppresses the pending start;
  a start already in flight is followed by a fenced termination command.
- The Customer and active users in the selected route receive a content-free
  lifecycle notification. Assigned production and QC users are included when
  applicable. Tracking views derive the terminal status from the existing
  metadata projection.
- Historic activity shows that the Customer cancelled the request and records
  the supplied reason. The reason is not copied into notification subjects,
  telemetry or logs.

## Personal profile acceptance criteria

- The profile displays `Name`, account ID, role, workspace access, governed
  organisation assignment and session state.
- Every signed-in user can maintain optional Team or business area, Rank or
  grade, Service number and Additional information fields.
- Profile fields are plain text, trimmed, individually bounded and writable only
  by the signed-in identity. Empty input clears the optional value.
- Personal profile fields never change role, scope, organisation membership,
  routing permissions, statistics scope or Camunda candidate groups.
- Profile updates require CSRF protection and optimistic concurrency.
- Service number and additional information are returned only on the signed-in
  profile endpoint and are excluded from session payloads, notifications,
  operational analytics and application logs.

## Customer register and account-request acceptance criteria

- The active register is titled `Current requests`.
- Each register has subtle, accessible column headers for Reference, Request,
  Status, Current owner, Required by and Actions, aligned with its row layout.
- Compact layouts retain a meaningful accessible header without forcing a wide
  desktop table onto narrow screens.
- The public account-request form labels the identity field `Name`, not
  `Display name`; the internal API and database field remain stable to avoid an
  unnecessary compatibility migration.

## Security and failure behaviour

- Object ownership, current state and version are rechecked on the locked row.
- Camunda I/O never occurs while a database transaction is held.
- Durable cancellation commands are idempotent and fenced by outbox lease owner
  and generation. A terminated process proves success after an uncertain call.
- Cancellation notification audiences are snapshotted from server-owned routes,
  roles and assignments. The browser cannot nominate recipients.
- The UI warns that cancellation closes the request and cannot be undone.
