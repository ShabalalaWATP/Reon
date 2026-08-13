# Request and workflow authorisation hardening

## Decision

Request-event audience is server-owned persisted data. Customer request history
contains only `CUSTOMER_AND_STAFF` events. `CURRENT_OWNER` coordination,
ownership-return requests and support or workflow-internal events remain available
to authorised staff but are excluded from every Customer history page, including
cursor pagination.

Every delivery completion boundary locks and revalidates the current actor and all
active request participants. The single Lead must match the request Lead, and the
Lead plus every Contributor must still be active Delivery Specialists with a
current membership of the exact assigned delivery team. Assignment validates the
complete proposed participant set by the same rule. Stale participant IDs are not
projected into actions or notifications.

The global organisation reference endpoint is staff-only. Customer submission
continues to use its server-owned configured root route and does not require global
organisation or staffing topology.

Workspace collaboration links are canonical public HTTPS URLs. Credentials,
fragments, controls, backslashes, non-443 ports and local, private or link-local
destinations are rejected before persistence. Platform Administration membership
changes reuse the normal roster disposition guard before ending or moving a
membership.

## Acceptance criteria

- Customer history never returns a `STAFF_ONLY` event, across all pages.
- Staff tracking retains the complete authorised event history.
- Legacy `CURRENT_OWNER` and internal events are backfilled to `STAFF_ONLY`.
- Dispatch and finalisation fail closed after any Lead or Contributor becomes
  inactive, changes role or leaves the assigned team.
- Action and notification projections omit stale participants.
- Customers cannot enumerate global organisation or staffing data.
- Collaboration URLs have one canonical public HTTPS representation.
