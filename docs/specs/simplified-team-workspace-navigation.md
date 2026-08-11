# Simplified team workspace navigation

## Purpose

Give each staff unit one obvious operational destination. The team workspace
contains the unit's work queue, while secondary planning and handover tools do
not compete with the daily request workflow in the MVP interface.

## User experience

- A staff user with a current workspace sees one named workspace link in the
  primary navigation instead of separate queue and workspace links.
- The workspace includes an actionable `Work queue` view. Users can claim and
  complete the same authorised work they previously handled on the standalone
  role queue.
- Delivery-team workspaces retain Overview, Work queue, Board, Calendar,
  People, Statistics and Activity.
- Routing workspaces retain Overview, Work queue, Calendar, People, Statistics
  and Activity.
- Planning and Handover are removed from the primary workspace navigation and
  overview. Direct visits to those old workspace views return to Overview.
- The Board presents package detail, blockers, dependencies, reservations and
  activity directly. It does not fetch planning-cockpit data or link to a
  removed Planning page.
- Users without a current workspace retain their role queue as a safe fallback.

## Data and security boundaries

- This change does not broaden work-item visibility or action authority. The
  embedded queue uses the existing API and passes the exact authorised unit ID.
- Server-side role, object and action authorisation remains authoritative.
- Existing planning and workspace-record data is retained. Simplifying the MVP
  interface does not delete audit history or stored records.
- Legacy standalone queue routes remain available for bookmarked links and
  notifications, but are no longer duplicated in primary navigation when a
  workspace is available.

## Acceptance criteria

1. A user with a workspace sees one workspace destination in the sidebar.
2. Work can be claimed and completed from the workspace Work queue.
3. The workspace does not display Planning or Handover tabs or overview panels.
4. Old Planning and Handover workspace URLs redirect to Overview.
5. Routing and delivery workspaces retain their role-appropriate operational
   views.
6. A staff account without a workspace can still reach its role queue.
7. Board cards and inspectors contain no dead Planning links or hidden Planning
   dependency.
