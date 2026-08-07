# Workspace state evidence

Recorded on 7 August 2026. The 188-test frontend suite covers loading, empty,
success and recoverable-error presentation throughout the critical workspaces.
Conflict, stale-version and permission outcomes are also exercised at the API
and form boundaries.

| Workspace | Principal evidence |
| --- | --- |
| Authentication and route policy | `app/auth-flow.test.tsx` |
| Customer register and request detail | `requester-flow.test.tsx`, `branch-states.test.tsx` |
| Drafts and mandatory form | `draft-flow.test.tsx`, `requester-flow.test.tsx` |
| Staff queues and routing | `staff-flow.test.tsx`, `routing-options-flow.test.tsx` |
| Product review | `staff-deliverable-flow.test.tsx` |
| Metadata tracking | `tracking-flow.test.tsx` |
| Statistics | `StatisticsPage.test.tsx` |
| Team overview and People | `TeamWorkspacePage.test.tsx` |
| Calendar and capacity | `CalendarPage.test.tsx` |
| Board and packages | `TeamBoardPage.test.tsx` |
| Planning and iterations | `TeamPlanningPage.test.tsx` |
| Platform administration | `admin-flow.test.tsx` |
| Organisation | `organisation-flow.test.tsx` |

The browser traces add visual evidence for empty queues, successful released
requests, mandatory validation, populated roster, empty and completed board
columns, calendar availability, scoped statistics and the Administrator register.
