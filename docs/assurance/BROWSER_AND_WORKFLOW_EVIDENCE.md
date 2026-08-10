# Browser and workflow evidence

This file contains current visual orientation and dated assurance records. The
source-controlled screenshots below were captured from the internally matched,
running synthetic QA Compose application on 9 and 10 August 2026. The web, API,
PostgreSQL and Camunda containers were healthy, and the authenticated captures
produced no unexpected browser console error. Playwright CLI used Chromium with
a 1,440 by 1,000 CSS-pixel viewport. The images prove that the
documented screens rendered, but are not a source-to-image attestation,
accessibility acceptance or evidence that every Product Evolution gate is
closed.

The workflow and cross-browser records after the screenshots are historical MVP
evidence. They do not prove the later managed-product or guided-configuration
capabilities and must not be used to close Product Evolution browser or
acceptance gates.

## Route lifecycle and chart presentation, 10 August 2026

The rebuilt local production containers were exercised with a JIOC routing
session. Tracking showed title-first rows, linked references, exact selected
routes and delivery lifecycles. Selecting **Russian Troop Movements** opened
`/tracking/{requestId}` and displayed the original submitted request in a
read-only view without workflow actions or product controls.

The same session opened Statistics at the JIOC grant root. Current status,
due-date risk and active request age rendered as donut charts, and completed
stage duration rendered median and 90th-percentile ranges. Legends, textual
summaries and table disclosures remained present. The browser console contained
no warnings or errors.

## Current application screenshots

The images deliberately contain only synthetic fixtures. Nine representative
screens are retained in source control. Replace an image when its corresponding
surface changes materially instead of accumulating a screenshot for every test
state.

### Login

Blank login form in the graphite ISTARI visual system. No credential is shown.
The green `OFFICIAL` strip is visible at the top and the secondary forgotten
password action remains subordinate to sign-in.

![ISTARI login screen](../assets/screenshots/login.png)

### Password assistance

The anonymous assistance state accepts a governed work email and returns the
same non-disclosing response. This synthetic example notified all active
Platform Administrators and exposed only account `admin2`, not the submitted
email, in their mandatory account-security notification.

![Forgotten-password assistance](../assets/screenshots/password-assistance.png)

### Global classification administration

Elevated Platform Administrator `admin1` changed the versioned marking from
`OFFICIAL` to `OFFICIAL-SENSITIVE`. The persistent strip changed to blue and the
page confirmed the global update. The live PostgreSQL path initially exposed an
enum persistence mismatch that the SQLite tests could not reveal; the mapping
was corrected, regression-tested and successfully repeated before the retained
setting was restored to `OFFICIAL`.

![Platform classification administration](../assets/screenshots/platform-classification-admin.png)

### Structured request form

Customer `admin2` on the blank service-request form. The visible required
markers and explanatory text show that every submission field is mandatory,
while private incomplete drafts remain possible.

![New service request form](../assets/screenshots/new-service-request-form.png)

### Customer request tracking

Customer `admin2` on `My requests`. The synthetic in-progress row shows current
stage, owner role, service age, required-date proximity and a direct request
link. Authenticated product download and feedback appear here after
dissemination; the historical completed-journey evidence below proves that
separate state-changing path.

![Customer request tracking dashboard](../assets/screenshots/customer-request-dashboard.png)

### Team workflow board

OSG Team Manager `admin8` on the Team workspace Board. The view identifies the
cards as Camunda-derived projections and exposes filtering, saved-view and
Kanban controls without allowing drag-and-drop to bypass named workflow actions.

![OSG Team workflow board](../assets/screenshots/team-workflow-board.png)

### Routing workspace

JIOC Manager `admin74` on the JIOC Overview. The routing workspace provides a
single operational entry point to its Queue, Calendar, People, Statistics,
Handover and Activity views. It deliberately does not expose delivery-team
planning or an additional Manager approval stage.

![JIOC routing workspace overview](../assets/screenshots/routing-workspace-overview.png)

### Shared team calendar

OSG Team Manager `admin8` on the shared Calendar. Every current member can add
their own leave, course, training and availability records. Exact-team Managers
can also add unit events and, for delivery teams only, link commitments to
eligible tickets. Month, week and agenda modes share the same governed records.

![OSG Team shared calendar](../assets/screenshots/team-calendar-manager.png)

### Effective-dated team roster

OSG Team Manager `admin8` on People. Current and historical Manager and Member
positions remain visible. Manager appointment, transfer and end actions require
effective dates and reasons; platform administrators retain organisation-wide
control.

![OSG Team effective-dated roster](../assets/screenshots/team-people-manager.png)

## Automated workspace-state coverage

The current 326-test frontend suite passed on 10 August 2026 with 99.41 per cent
line and 95.01 per cent branch coverage. It includes access-assistance,
classification, routing-workspace,
effective-membership, self-service calendar, Lead and Contributor, collaboration
and hierarchy-statistics regressions. The following table began as the candidate
index recorded on 7 August 2026 and now identifies the principal current test
locations. The frontend suite covers loading, empty, success and
recoverable-error presentation throughout the critical workspaces. Conflict,
stale-version and permission outcomes were also exercised at API and form
boundaries.

| Workspace | Principal evidence |
| --- | --- |
| Authentication and route policy | `app/auth-flow.test.tsx` |
| Password assistance and classification | `app/password-assistance-flow.test.tsx`, `app/admin-flow.test.tsx`, `components/classification-control.test.tsx` |
| Customer register and request detail | `requester-flow.test.tsx`, `branch-states.test.tsx` |
| Drafts and mandatory form | `draft-flow.test.tsx`, `requester-flow.test.tsx` |
| Staff queues and routing | `staff-flow.test.tsx`, `routing-options-flow.test.tsx` |
| Product review | `staff-deliverable-flow.test.tsx` |
| Metadata tracking | `tracking-flow.test.tsx` |
| Statistics | `StatisticsPage.test.tsx` |
| Team overview and People | `TeamWorkspacePage.test.tsx` |
| Routing workspaces and queues | `RoutingWorkspacePage.test.tsx` |
| Workspace collaboration | `TeamWorkspacePage.test.tsx`, `RoutingWorkspacePage.test.tsx` |
| Calendar and capacity | `CalendarPage.test.tsx` |
| Board and packages | `TeamBoardPage.test.tsx` |
| Planning and iterations | `TeamPlanningPage.test.tsx` |
| Platform administration | `admin-flow.test.tsx` |
| Organisation | `organisation-flow.test.tsx` |

## Historical MVP environment

Recorded on 7 August 2026 against the production React image, FastAPI,
PostgreSQL 17.9 and Camunda 8.9.14. Installed browser versions were Chrome
151.0.7922.75, Edge 151.0.4129.59 and Firefox 153.0.

## Complete Customer and delivery journey

Request `SR-2026-A5660D8D` completed through the real application and workflow:

1. Customer `admin2` proved mandatory-field rejection, then submitted a complete
   request and saw it in the tracking register.
2. JIOC `admin4` recorded related records and selected DIGOC.
3. Command user `admin5` selected NCGI-A Ops, then Ops user `admin6` selected
   OSG Team.
4. OSG Manager `admin8` assigned Lewis Ferguson (`admin11`).
5. The Analyst requested additional information. The Customer response was
   retained in the dashboard and returned to the same Analyst assignment.
6. The Analyst submitted a product. OSG Manager approved it and QC user
   `admin15` separately approved and disseminated it to a required recipient.
7. The Customer saw `Completed`, the full activity and clarification history,
   downloaded the authenticated product link and submitted one-time mandatory
   rating and comments.

No JIOC, command or Ops approval was inserted into the return path.

## Alternative route proof

`scripts/run-local-app-journey.py` completed request `SR-2026-4D12E2BA` through
SYGOC, Nimbus Ops and Beacon Team. Archie Gemmill produced the product and the
Customer download was verified. The content-free result is retained at
`output/playwright/alternative-app-journey.json`.

`scripts/smoke-camunda.ps1` separately completed both the OSG route with two
clarification loops and an alternative staffed route. Candidate groups remained
distinct and no alternative route fell back to OSG.

## Team and management journeys

- OSG Team showed three Managers and seven Analysts.
- A Manager ended and re-added Ben Doak using mandatory reasons. Current and
  historical membership remained visible.
- Board, accessible table, WIP limits, saved filters and required work-package
  fields rendered from workflow and team planning records.
- Calendar month, week and agenda views, privacy, recurrence and capacity
  controls were exercised.
- Statistics showed OSG only to the OSG Manager, JIOC and child commands to the
  JIOC Manager, and only explicit DIGOC, SYGOC and MYGOC scopes to the shared
  command account.

## Compatibility result

Critical pages rendered and remained navigable in current Chrome, Edge and
Firefox at desktop and narrow widths. Screenshots are retained in
`output/playwright`. Customer authentication, tracking, released-product,
clarification, feedback and mandatory-form validation passed in all three
browsers and are retained as Playwright CLI traces:

- `chrome-customer-acceptance.trace`;
- `edge-customer-acceptance.trace`;
- `firefox-customer-acceptance.trace`.

Additional Chrome traces cover the Team Manager queue, roster, calendar, board
and exact-team statistics; JIOC metadata tracking and JIOC-only statistics; and
the then-current 72-account Administrator register, step-up and create-user
form. Trace names, browser versions, scenarios and SHA-256 values are recorded in
`output/playwright/browser-acceptance.json`.

The complete end-to-end state-changing delivery journey was repeated in Edge
151.0.4129.59 as request `SR-2026-0D8A4A96` on the OSG route and Firefox 153.0
as request `SR-2026-79C5D79F` on the SYGOC, Nimbus Ops and Beacon Team route.
Both journeys included named claims and routing decisions, Team Manager
assignment, Analyst clarification, Customer response, Analyst product
submission, Manager review, separate QC approval, dissemination, authenticated
download and required feedback. PostgreSQL reconciliation found both requests,
products and Camunda workflow instances completed, one clarification thread
with two messages in each, and ratings of five and four respectively.

The raw traces, network logs, completion screenshots and downloaded products are
retained in `output/playwright`. Their hashes are recorded in
`output/playwright/browser-acceptance.json`. The validated final reports are:

- `output/playwright/cross-browser-staff-acceptance.html`;
- `output/playwright/cross-browser-staff-acceptance.junit.xml`.

The final report SHA-256 values are
`F035EEE71CEBACB3345CBC52A80164BF5013AF2D0CF837C605A41CA52B6EF080` for
the HTML report and
`F5B727A85E40C97C85F23539B17818D2EC23A3162A90CCC7A8E154B25B9ACA6A`
for the JUnit report. The manifest SHA-256 is
`548B8D2D2BE0DD06D48D61904FBD6DC21E81427124B8D6BBF870182A01908E96`.

Run `uv run --directory apps/api python
../../scripts/render-browser-acceptance.py` to verify every evidence hash and
regenerate both reports. DOD-31 and DOD-44 are evidence-ready. Product-owner and
representative-user acceptance remain separate human decisions.

## Operator-orientation browser check

On 8 August 2026, the current React source was served locally and inspected in
Chromium against the existing synthetic local API. The Customer workspace showed
exactly one `aria-current="page"` item on both `/requests` and `/requests/new`.
At the time of this historical capture, the account dialog exposed `admin2`,
Customer role, the former Requesting Area A seed scope and session expiry. The
current product replaces that fictional scope with Customer workspace access
and links to a complete profile. The dialog closed on Escape and route change,
remained within a 640-pixel viewport, and keyboard focus produced a visible
two-pixel outline.

This focused check covers the changed shell at desktop and narrow width. It does
not replace the recorded three-browser baseline or constitute representative
accessibility acceptance. Routing breadcrumb behaviour is covered by component
accessibility tests. The rebuilt target API subsequently returned `JIOC [JIOC]`
and exactly the three configured Command children from PostgreSQL. A complete
current-source target journey also passed through SYGOC, Nimbus Ops and Beacon
Team. Representative routing and accessibility acceptance remain required.

## Target-scale cursor browser check

On 8 August 2026, Chromium controlled through the Playwright CLI exercised the
production-built React and FastAPI images against the clean 2,500-row PostgreSQL
17.9 fixture at migration `0019_runtime_scaling`.

- Customer `admin2` rendered 50 requests and 50 private drafts, then loaded a
  cursor page. One hundred drafts remained visible and both older-request and
  older-draft responses returned successfully.
- JIOC user `admin4` rendered and retained 100 staff-work items, then retained
  100 route-scoped tracking rows after loading another page.
- OSG Manager `admin8` opened the OSG Board and moved from 25 cards on page one
  to 25 cards on page two using the opaque Board cursor.
- Platform Administrator `admin1` retained 100 user-register rows after loading
  another page.

Cursor responses took 31.6 to 51.7 ms in this local topology. The only console
error was the expected anonymous `/auth/me` HTTP 401 probe before each login;
authenticated pages produced no unexpected console error. The target-scale
check is Chromium-only and read-oriented. It supplements, rather than replaces,
the historical three-browser state-changing workflow acceptance above.

The content-free traces and screenshots are under
`output/playwright/runtime-scale`. Trace SHA-256 values are:

- Customer pagination: `5DBD5F150B75C2F63A352247755AAC81293063F64A65D10574FDC140F5C54F63`;
- routing pagination: `DAD29C589AF9C67BDCA11D77B1CE25750064DE462D793655167AA960536F781D`;
- Board pagination: `274F2475D4BD82657C9D374552AE3B8A052FB1BCA5692E862E8F3327E05B450C`;
- administration pagination: `CD089B2BC70E76DBFD6E154B49497CD8FEA6CC998755C9A381185EFBB0464F2E`.

`output/load/runtime-scale-manifest.json` binds every trace, network log,
screenshot, fixture, plan result and HTTP result to a content hash. These local
generated files must be copied to the approved immutable evidence store when a
candidate release is qualified.

## Team-operations candidate browser check

On 10 August 2026, the rebuilt Compose candidate at migration
`0030_team_operational_skills` was inspected in the in-app Chromium browser.

## Role-aware action-link regression, 10 August 2026

The local Compose candidate was rebuilt and migrated to
`0031_role_aware_action_links`. PostgreSQL confirmed that the active Russian
Troop Movements projection was assigned to admin4 and stored the role-owned link
`/triage?requestId=28f0b5c4-e459-441f-80eb-c4620162b182`.

The existing in-app browser session was reloaded against the rebuilt candidate.
The following visible behaviour was then exercised as Scott McTominay (admin4):

1. Primary navigation showed `My actions`, `JIOC queue` and `JIOC workspace` as
   separate destinations.
2. My actions showed Russian Troop Movements as `Assigned to you`.
3. Open navigated to the exact stored JIOC queue link.
4. The JIOC queue selected SR-2026-28F0B5C4 and rendered Russian Troop Movements,
   its full request record, previous-request matching and the human decision
   form. It did not redirect to Overview or silently select another ticket.
5. The JIOC queue navigation item exposed `aria-current="page"` and the active
   styling class on the selected route.

The migration was then downgraded once and re-upgraded against the live
PostgreSQL dataset. The repaired personal audience and exact role-owned link
were present after the rehearsal.
Every service was healthy, including PostgreSQL 17.10, Camunda 8.9.14, the API,
worker, web tier and antivirus services.

- OSG Manager `admin8` saw linked assignment, clarification, review, due-risk,
  capacity, calendar, people, handover, activity and exact-team statistics on the
  workspace home.
- The OSG Board exposed active lanes first, collapsed exception and terminal
  groups, a table alternative and complete filtered column totals. Expanding the
  terminal group returned two completed requests and the side inspector loaded
  the authorised Customer requirement and delivery context.
- JIOC Manager `admin74` saw a routing-only decision home, its Manager/Member
  roster and one exact-unit JIOC routing decision. The unit Queue contained that
  same decision and did not expose delivery Kanban or allocation controls.
- No unexpected browser console warning or error was recorded. One safe 404 in
  the first OSG inspector pass exposed an overly narrow terminal-history policy;
  exact-team Manager history access was corrected, regression-tested and then
  verified successfully against the same PostgreSQL record.

This focused current-candidate check is read-oriented and Chromium-only. It does
not replace representative-user, cross-browser or accessibility acceptance.
