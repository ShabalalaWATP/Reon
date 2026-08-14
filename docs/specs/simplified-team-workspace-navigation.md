# Unified team workspace navigation

Status: current implemented navigation contract
Last reviewed: 14 August 2026

## Purpose

Give each staff unit one obvious operational destination. The named workspace
contains the unit's actionable queue and role-appropriate collaboration views.

## User experience

- A staff user with a current workspace sees one named workspace link in primary
  navigation instead of duplicate queue and workspace links.
- The workspace includes an actionable `Work queue`. Users can claim and complete
  only work authorised for the exact unit and actor.
- Delivery-team workspaces contain Overview, Work queue, Board, Calendar, People,
  Statistics and Activity.
- Routing workspaces contain Overview, Work queue, Calendar, People, Statistics
  and Activity.
- The Board distinguishes workflow-derived Service Request cards from the
  collapsible internal Work Package board used by the Analyst team.
- Users without a current workspace retain their role queue as a safe fallback.

## Data and security boundaries

- Embedding the queue does not broaden work-item visibility or action authority.
  It uses the exact authorised unit identifier.
- Server-side role, context, object and action authorisation remains authoritative.
- A Service Request card changes stage only through a named workflow action.
- An internal Work Package card may move through its own reasoned and versioned
  coordination states, but cannot alter Camunda or Customer-visible request state.
- Standalone queue routes remain available for notification and action deep
  links, but are not duplicated in primary navigation when a workspace exists.

## Acceptance criteria

1. A user with a workspace sees one workspace destination in the sidebar.
2. Work can be claimed and completed from the workspace Work queue.
3. Routing and delivery workspaces expose only their current role-appropriate
   operational views.
4. A staff account without a workspace can still reach its authorised role queue.
5. Service Request and Work Package boards are labelled, functionally separate
   and accessible without drag gestures.
6. The Work Package section is collapsible and does not advance workflow.
