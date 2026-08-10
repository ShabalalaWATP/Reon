# Tracking lifecycle and analytical visuals

Status: implementation candidate, 10 August 2026.

## Problem

The Tracking register exposes a reference, current owner and a text route, but
not the request title. Operators cannot reopen a request after their routing
task has moved downstream, and the route does not explain how the request sits
within the delivery lifecycle. The shared Statistics surface has accessible
data but relies heavily on small horizontal bars and tables.

## Users and scope

- JIOC routing users track requests whose pinned route contains their exact JIOC
  unit.
- Command routing users track requests whose pinned route contains one of their
  exact command memberships.
- Operations routing users track requests whose pinned route contains one of
  their exact Ops memberships.
- Statistics remain constrained to the reporting roots and descendant units in
  the existing server-issued scope. A visual must never broaden the dataset.

## Tracking behaviour

1. Every register row shows the request title as its primary label and the
   immutable reference as secondary identity.
2. The reference, title and explicit `Open request` action link to
   `/tracking/{requestId}`.
3. The register shows the selected organisation route as a connected sequence
   and a five-stage lifecycle: routing, production, team check, quality and
   release, and Customer delivery. Cancelled or not-progressed requests end in a
   clearly labelled closed state.
4. The detail route returns the submitted request fields and lifecycle metadata
   through a dedicated read-only endpoint.
5. The detail endpoint repeats the same exact route-membership predicate as the
   register. It returns concealed not-found for non-routing roles, removed
   memberships, sibling units and requests outside the actor's route.
6. The tracking detail excludes workflow actions, clarification conversations,
   feedback, product content and product download links.
7. No tracking route permits a mutation. Current operational work remains in
   the role-owned queue.

## Statistics behaviour

1. Current status, due-date risk and active age use three restrained donut
   charts with labelled legends, totals and the existing accessible data table.
2. Completed stage duration uses a range graphic showing median and 90th
   percentile against a common scale, plus the existing accessible table.
3. Throughput and child-unit comparisons remain because they answer different
   operational questions: flow over time and demand by direct child.
4. Visual colour is supplementary. Labels, values and table equivalents remain
   available to assistive technology.
5. Empty, loading, error, reduced-motion and narrow-screen states remain
   explicit.

## Acceptance criteria

- A routed request title is visible in Tracking without opening the record.
- A JIOC user can open an authorised historical request after it has moved to a
  downstream unit and see the submitted request details read-only.
- A sibling command user receives a concealed denial for the same detail.
- Both register and detail show an understandable organisation route and
  lifecycle graphic.
- Three distribution donuts and a stage-duration range chart render for every
  role using the shared, server-scoped Statistics dashboard.
- Chart tables contain the same labels and values as the visual presentation.
- Backend and frontend line and branch coverage remain at least 95 per cent.

## Non-goals

- Reopening, rerouting or acting on work from Tracking.
- Exposing clarification bodies or unreleased or released service products.
- Adding a second analytics API or client-side access-control filter.
- Inferring future organisation destinations before a human selects them.
