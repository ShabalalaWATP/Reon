# Current user stories

Status: current product behaviour and acceptance catalogue
Last reviewed: 10 August 2026

This catalogue describes ISTARI Service from the point of view of the people who
use and operate it. It uses plain English first. Technical identifiers are added
only where they help testers and developers connect a story to a route, policy or
workflow task.

## Contents

1. [How to use these stories](#how-to-use-these-stories)
2. [People and responsibilities](#people-and-responsibilities)
3. [Rules shared by every story](#rules-shared-by-every-story)
4. [Customer stories](#customer-stories)
5. [CRIOC routing stories](#crioc-routing-stories)
6. [Command coordination stories](#command-coordination-stories)
7. [Ops routing stories](#ops-routing-stories)
8. [Team Manager stories](#team-manager-stories)
9. [Team Analyst stories](#team-analyst-stories)
10. [QC Manager stories](#qc-manager-stories)
11. [Platform Administrator stories](#platform-administrator-stories)
12. [Workspace Manager and Member stories](#workspace-manager-and-member-stories)
13. [Runtime operator and support stories](#runtime-operator-and-support-stories)
14. [Cross-role scenarios](#cross-role-scenarios)
15. [Traceability](#traceability)

## How to use these stories

Each story has four parts:

- **Need** states what the person is trying to achieve.
- **Expected behaviour** describes the successful path.
- **Acceptance checks** are observable outcomes that can be tested.
- **Safety and failure behaviour** explains what must happen when access, data or
  a dependency is wrong.

The stories describe current product behaviour. Delivery history belongs in the
[development story](DEVELOPMENT_STORY.md). Architectural reasons belong in the
[ADRs](adr/). Dated test results belong in [assurance](assurance/).

## People and responsibilities

| Person | Main responsibility | Primary workspace |
|---|---|---|
| Customer | State a complete need and receive the released product | My requests |
| CRIOC Routing User | Review new demand and choose a direct command | CRIOC routing queue |
| Request Coordination User | Coordinate the request and choose a direct Ops group | Incoming requests |
| Ops Routing User | Choose a direct delivery team | Ops routing queue |
| Team Manager | Assign Analysts, oversee delivery and check the product | Team queue and team workspace |
| Team Analyst, Lead | Produce and submit the accountable product | Production queue and product package |
| Team Analyst, Contributor | Collaborate on an assigned request without owning the Lead task | Assigned request and team planning |
| QC Manager | Perform final review and release the approved product | QC queue |
| Platform Administrator | Maintain people, teams and safe platform configuration | Administration |
| Workspace Manager | Maintain the exact unit's roster, calendar and handover information | Organisation workspace |
| Workspace Member | Work in the exact unit and maintain personal availability | Organisation workspace and personal calendar |
| Runtime operator | Deploy, observe, back up and restore the service | Controlled operational tooling |

The representative workflow role and the workspace position are separate. For
example, a person can be a CRIOC Routing User and also hold the Manager position in
the CRIOC workspace. The workflow role controls routing actions. The workspace
position controls roster and collaboration administration.

## Rules shared by every story

1. The account must be active and the session must be valid.
2. FastAPI checks permission for the exact object and action. A hidden button is
   never the security boundary.
3. A user sees only their own request, exact assignment, selected route or
   authorised organisation branch.
4. Stale pages and duplicate submissions cannot silently repeat an action.
5. Human decisions that change workflow state require the current task, expected
   request version and any mandatory reason.
6. Sensitive changes require CSRF protection and, where stated, fresh step-up
   authentication.
7. Request narrative, product content, passwords, tokens and sessions are not
   written to ordinary application logs.
8. Errors explain the next safe action without confirming inaccessible records.
9. Current personal events appear in the current team calendar unless the user
   marks the event private. A private event shows colleagues only `Busy` and its
   time.
10. Dates, routes, assignments, approvals and released products remain
    attributable in history and audit records.

## Customer stories

### CUST-01: Request an account

**Need:** As a prospective Customer, I want to request an account from the sign-in
page so that an Administrator can review my access need.

**Expected behaviour**

- The person chooses `Request account` without needing an existing session.
- Name, work email and the required request details are validated.
- ISTARI stores a bounded account-request record and notifies Administrators.
- The response does not reveal whether a similar account already exists.

**Acceptance checks**

- Missing or malformed fields are identified next to the field.
- Repeated submission is rate limited and does not create uncontrolled records.
- An Administrator can accept or reject the request with an attributable reason.
- Acceptance creates an account through the same governed identity controls as
  manual provisioning.

**Safety and failure behaviour:** Submitted details are not placed in Camunda or
ordinary logs. A notification failure does not expose the applicant's email.

### CUST-02: Sign in and recover access

**Need:** As an account holder, I want a clear sign-in and password-assistance
route so that I can enter the service or alert support when I cannot remember my
password.

**Expected behaviour**

- The user enters the assigned account ID and password.
- Successful authentication starts a protected server-side session.
- `Forgotten password?` accepts the account email and creates a bounded
  Administrator notification when it matches an active account.
- The public response is the same whether the email matches or not.

**Acceptance checks**

- Disabled accounts cannot start a session.
- Repeated failures share a PostgreSQL-backed rate limit across API replicas.
- Session expiry is shown clearly and returns the user to sign-in.
- Passwords, submitted emails and session tokens never appear in logs.

### CUST-03: Save a private draft

**Need:** As a Customer, I want to save an incomplete request privately so that I
can complete it later without starting the workflow.

**Expected behaviour**

- A draft can be saved before every submission field is complete.
- Only its owning Customer can read, change or delete it.
- A draft is clearly labelled and has no Camunda process instance.
- Submitting the completed draft creates an immutable submitted revision.

**Acceptance checks**

- Another Customer, staff user or Platform Administrator cannot open the draft.
- A stale draft update is rejected rather than overwriting newer work.
- Deleting a draft does not affect submitted requests.

### CUST-04: Submit a complete request

**Need:** As a Customer, I want a structured form that requires the information
needed for delivery so that my request can be understood without avoidable email
exchanges.

**Expected behaviour**

- Every submission field is mandatory.
- Four plain-language sections show the remaining required-field count and mark
  each section complete when its values are valid.
- The Customer supplies the need, question, outcome, context, relevant period,
  urgency, required date, intended use, product preference, success measures,
  constraints, available supporting information and handling instructions.
- Internal team, routing organisation and recipient fields are not shown.
- Focused narrative inputs show their character allowance before the server
  limit is reached.
- A successful submission returns a stable request reference and appears in
  `My requests`.

**Acceptance checks**

- The submit control is unavailable until client-side validation succeeds.
- Progress links move keyboard and pointer users directly to the corresponding
  form section without changing entered values.
- Matching server validation is authoritative and returns field-specific errors.
- Double-click, browser retry and repeated network submission create one request.
- The initial immutable revision and workflow-start intent commit together.

### CUST-05: Understand progress

**Need:** As a Customer, I want a simple tracking dashboard so that I know whether
my request needs input, is being worked on or has completed.

**Expected behaviour**

- `My requests` shows title, reference, current status, required date and action
  needed.
- Opening a request shows its submitted information, plain-English journey,
  current responsible organisation, activity history and available actions.
- Engine-specific terms and internal candidate-group identifiers are not shown.
- Notifications deep-link to the exact accessible request action.

**Acceptance checks**

- The Customer cannot see another Customer's request by changing the URL.
- A notification for an ended action opens a safe ended-action message.
- Temporary workflow lag is shown as pending, not as fabricated progress.

### CUST-06: Answer a question

**Need:** As a Customer, I want questions from CRIOC or the assigned Lead to appear
inside my request so that the full exchange is kept with the work.

**Expected behaviour**

- The dashboard highlights that information is required.
- The question, reason, requester and response deadline are visible.
- The Customer submits an answer from the request page.
- The answer is appended to the history and work returns to CRIOC or the same Lead,
  depending on where the question began.

**Acceptance checks**

- The Customer cannot answer a closed, cancelled or already answered thread.
- A stale response page is rejected with a refresh instruction.
- The full exchange remains visible to authorised participants.

### CUST-07: Cancel an active request

**Need:** As a Customer, I want to cancel my request with a reason so that people
do not continue work that I no longer need.

**Expected behaviour**

- The cancellation control appears only in allowed active states.
- A meaningful reason is mandatory.
- Cancellation closes the applicable workflow path, updates the dashboard and
  notifies relevant participants.
- The reason and time remain in the activity history.

**Acceptance checks**

- Another Customer cannot cancel the request.
- A request already disseminated or terminal cannot be cancelled through a stale
  page.
- If Camunda is unavailable, ISTARI records a durable cancellation command and
  shows pending completion rather than reporting success early.

### CUST-08: Receive the product and give feedback

**Need:** As a Customer, I want the released product in my dashboard and a simple
feedback form so that I can use the result and rate the service.

**Expected behaviour**

- A released PDF, DOCX or PPTX has an authenticated download action.
- An approved external product has a labelled HTTPS link.
- The request identifies the released product and release time.
- The Customer submits one service rating and optional comments.

**Acceptance checks**

- Product bytes are never exposed as a public storage URL.
- Download rechecks ownership and release state every time.
- Unreleased and withdrawn product versions are not downloadable.
- Feedback is accepted once and only for the owning completed request.

### CUST-09: Maintain a personal profile and calendar

**Need:** As any authenticated user, including a Customer, I want a useful profile
and personal calendar so that my account contains current information and my
availability is easy to manage.

**Expected behaviour**

- The profile can contain name, team or organisation, rank, service number and
  additional personal information within bounded fields.
- Every account can add, edit and cancel personal calendar events.
- A user with a current workspace membership sees personal events automatically
  represented in that team's calendar.
- A user without a team keeps a personal-only calendar.

**Acceptance checks**

- Personal information is editable only by the account holder or an authorised
  Administrator using the dedicated administration path.
- Private calendar entries disclose only busy time to current colleagues.

## CRIOC routing stories

### CRIOC-01: Review a newly submitted request

**Need:** As a CRIOC Routing User, I want new requests in a shared CRIOC queue so
that one named person can review and direct each request.

**Expected behaviour**

- An unclaimed item is described as awaiting CRIOC action.
- A CRIOC user claims the item before recording a decision.
- The reviewer can read the submitted revision and current request history needed
  for routing.
- The reviewer can request information, close with a reason or select one direct
  command.

**Acceptance checks**

- A non-CRIOC account cannot list, claim or complete the task.
- Two CRIOC users cannot both become the assignee.
- The selected command is revalidated as a current effective direct child.
- The decision, actor, destination and reason are audited.

### CRIOC-02: Examine possible related requests

**Need:** As a CRIOC reviewer, I want a compact optional comparison with previous
authorised requests so that I can record whether existing work is relevant.

**Expected behaviour**

- The comparison section starts collapsed.
- Automatic results use all submitted request fields and show explainable match
  evidence, not only title equality.
- Low-value results are bounded, scrollable and clearly labelled as possible
  matches.
- The reviewer records a human judgement without changing the route
  automatically.

**Acceptance checks**

- Search covers only requests the reviewer is authorised to see.
- A score never routes, closes or approves a request.
- Each new submitted request is added to the searchable projection.
- Semantic enrichment failure leaves full-text matching available.

### CRIOC-03: Track the selected branch

**Need:** As a CRIOC user, I want to follow a request after routing so that I can
see where it sits without becoming a product approver.

**Expected behaviour**

- Tracking shows title, reference, current stage, responsible organisation and a
  visual route journey.
- The reference and title open the authorised tracking detail.
- CRIOC can see aggregate statistics for itself and descendants.
- Product review and dissemination controls never appear.

**Acceptance checks**

- CRIOC sees JOCK, SYGOC and MYGOC branches, because they are descendants.
- The tracking permission does not expose unreleased files or Customer feedback.

## Command coordination stories

### CMD-01: Coordinate and route a request

**Need:** As a Request Coordination User in the selected command, I want to
understand the request and choose the appropriate direct Ops group.

**Expected behaviour**

- The shared queue identifies the command currently responsible.
- A named user claims the task before acting.
- The user can route to a direct Ops group, return to CRIOC, place on hold or close
  with the required reason.
- Every configured direct Ops group is selectable when effective.

**Acceptance checks**

- JOCK cannot choose an Ops group belonging to SYGOC or MYGOC.
- A stale or forged destination is rejected by FastAPI.
- Manager and Member positions have the same routing decision. The Manager
  position does not add an approval step.

### CMD-02: Place work on hold and resume it

**Need:** As the responsible command, I want to record a reasoned hold so that a
request can pause visibly without being lost.

**Expected behaviour**

- Hold reason and actor are mandatory and visible in history.
- Tracking and statistics identify the request as on hold.
- An authorised command user can later resume or close it.
- Camunda does not resume automatically from a date or inferred condition.

### CMD-03: See only the command branch

**Need:** As a command user, I want statistics for my organisation and its
descendants so that I can manage my demand without seeing sibling commands.

**Acceptance checks**

- JOCK sees JOCK, its Ops groups and delivery teams.
- JOCK cannot see SYGOC or MYGOC statistics.
- Each graph has readable labels and an accessible table equivalent.
- Small feedback cohorts are suppressed rather than identifying individuals.

## Ops routing stories

### OPS-01: Route to a delivery team

**Need:** As an Ops Routing User, I want to select one current direct team so that
the responsible Manager receives the assignment task.

**Expected behaviour**

- The queue identifies the selected Ops group as current owner.
- A named user claims the routing task.
- The user selects from direct teams only and records required capabilities.
- A staffed team receives a Team Manager assignment task.

**Acceptance checks**

- ACSA-B Ops can select SSG, Cedar or Quartz, but cannot select a team in another
  Ops branch.
- An unstaffed direct team remains visible as awaiting staffing and never borrows
  SSG users.
- The Ops user can return the request to the selected command.

### OPS-02: Manage branch demand

**Need:** As an Ops group, I want workload figures for my inbox and delivery teams
so that I can see demand, timeliness and current distribution.

**Acceptance checks**

- ACSA-B Ops sees ACSA-B Ops, SSG, Cedar and Quartz data.
- It does not see CRIOC totals, other commands or sibling Ops groups.
- Figures use content-free facts and do not reveal request narrative.

## Team Manager stories

### TM-01: Use a personal Home

**Need:** As a Team Manager, I want Home to separate my actions from team demand
so that I can quickly decide where to work next.

**Expected behaviour**

- Home greets the Manager by first name.
- `Your workload` contains personal actions and waiting items.
- The team workload is clearly labelled as combined organisation demand.
- Tiles link to assigned actions, team queue, team workspace, personal calendar,
  statistics and organisation directory.

### TM-02: Assign one Lead and several Contributors

**Need:** As a Team Manager, I want to name an accountable Lead and independently
select several supporting Analysts so that responsibility is clear without
limiting collaboration.

**Expected behaviour**

- The Lead list contains current eligible Analysts in the exact team.
- Contributing Analysts are ordinary checkboxes, not a modifier-key multi-select.
- Up to ten Contributors can be selected and a selected count is visible.
- Selecting a Lead visibly disables and removes that person from Contributors.
- A meaningful assignment reason is required.

**Acceptance checks**

- The API rejects a Lead who is also sent as a Contributor.
- Duplicate, inactive, ended-membership or other-team participants are rejected.
- The Camunda production task is assigned to the Lead only.
- Contributors receive object-level collaboration access but cannot complete the
  Lead task.
- Assignment history lists Manager, Lead, Contributors, reason and time.

### TM-03: Review the submitted product

**Need:** As a Team Manager, I want to review the exact submitted package so that
I can approve a good product or return useful changes.

**Expected behaviour**

- The current immutable package revision and artefacts are visible.
- Approve sends the same package to QC.
- Changes required needs an actionable reason and returns work to the same Lead.
- The Manager cannot alter the Analyst's submitted artefact in place.

### TM-04: Manage the exact team roster

**Need:** As a Team Manager, I want to add, transfer or end Analyst memberships so
that the workspace reflects current staffing.

**Expected behaviour**

- Managers appear first by default and every people-table column is sortable.
- Only an exact-team Manager can change membership.
- Effective date, reason and optimistic version are required.
- Current, scheduled and ended records remain visible as history.

**Acceptance checks**

- A Team Analyst cannot see membership mutation controls or call their APIs.
- A Manager cannot maintain a parent, child or sibling team without a separate
  exact grant.
- Ending membership does not erase assignment or audit history.

### TM-05: Use the shared team calendar

**Need:** As a Team Manager, I want a team calendar that combines member
availability and delivery commitments so that I can assign work realistically.

**Expected behaviour**

- Every current member's non-private personal activity appears automatically.
- Private activity shows only busy time.
- Clicking a day or `Add event` opens the same accessible event dialog.
- Only the Manager can create a request-linked delivery commitment for a named
  Analyst.

### TM-06: Plan work with the board

**Need:** As a Team Manager, I want a Kanban and planning workspace so that the
team can see work origin, status, priority, iteration, capacity and blockers.

**Expected behaviour**

- Request workflow items project onto the board without becoming a second
  workflow authority.
- Work packages can have owners, Contributors, estimates, acceptance criteria,
  dependencies and activity history.
- WIP limits and iteration controls are explicit and attributable.
- Opening a board item shows the originating request and current package detail.

### TM-07: Understand team statistics

**Need:** As a Team Manager, I want readable team-level analysis so that I can
identify demand, ageing, throughput, rework and capacity concerns.

**Acceptance checks**

- Charts include clear titles, labels, units and accessible table equivalents.
- Team figures do not expose sibling teams or rank individual Analysts.
- Small feedback cohorts remain suppressed.

## Team Analyst stories

### TA-01: Receive assigned work

**Need:** As a Team Analyst, I want only Manager-assigned production work in my
queue so that accountability is unambiguous.

**Expected behaviour**

- Analysts cannot claim open Team Assignment or Product Production tasks.
- The named Lead sees the production task in personal actions and production
  queue.
- Contributors see the authorised request and collaboration context without a
  Lead-completion action.

**Acceptance checks**

- UI controls and the API both deny Analyst claim attempts.
- A malformed open-task projection does not make the task visible or claimable.
- Removing assignment or effective membership removes future access while
  retaining history.

### TA-02: Produce a managed product

**Need:** As the Lead Analyst, I want to build a controlled product package so
that Manager and QC review the exact artefacts I submit.

**Expected behaviour**

- A package is tied to the assigned request and expected version.
- The Lead can upload labelled PDF, DOCX or PPTX files within configured limits,
  or add an approved HTTPS link.
- Uploaded bytes remain quarantined until type validation and malware scan pass.
- Submitting creates an immutable package revision for review.

**Acceptance checks**

- An unavailable or failed scanner never releases the file.
- Storage paths and quarantine identifiers are not public.
- A Contributor cannot submit the Lead's parent Camunda task.

### TA-03: Ask the Customer for information

**Need:** As the Lead, I want to ask a bounded question directly so that missing
detail can be resolved without restarting organisational routing.

**Expected behaviour**

- Question, reason and response deadline are mandatory.
- The Customer receives a dashboard action and notification.
- The conversation is stored on the request.
- The response returns to the same Lead.

### TA-04: Maintain personal availability

**Need:** As a Team Analyst, I want leave, courses and other events in my personal
calendar so that my team sees current availability without exposing private
details unnecessarily.

**Acceptance checks**

- The Analyst can create events without Manager assistance.
- Events appear in both personal and team calendars.
- `Private appointment` exposes only busy time to colleagues.
- The Analyst cannot attach a personal event to a request ticket.

## QC Manager stories

### QC-01: Review the approved package

**Need:** As a QC Manager, I want the exact Manager-approved package and review
history so that I can make the final release decision.

**Expected behaviour**

- The current package, artefacts, Manager outcome and handling context are visible.
- Changes required needs a reason and returns work to the same Lead.
- Approve advances to a separate dissemination action.
- The QC Manager cannot silently edit the reviewed package.

### QC-02: Disseminate safely

**Need:** As a QC Manager, I want to release a reviewed file or approved link to
the owning Customer so that dissemination is controlled and traceable.

**Acceptance checks**

- At least one valid recipient is required.
- Only clean promoted files and allowlisted HTTPS links can be released.
- Release records actor, package revision, recipients and time.
- The Customer sees the product only after successful release finalisation.

### QC-03: Understand QC demand

**Need:** As a QC Manager, I want QC workload and timeliness statistics so that I
can manage review and release without seeing unrelated operational branches.

**Acceptance checks**

- QC figures focus on items awaiting review, returned for change, ready to release
  and disseminated.
- Charts do not expose Customer feedback below the cohort threshold.

## Platform Administrator stories

### PA-01: Maintain an account

**Need:** As a Platform Administrator, I want to create, edit, deactivate and
reactivate accounts so that access reflects approved responsibility.

**Acceptance checks**

- Account ID, name, email, role, scope and active state are validated.
- Deactivation invalidates current sessions.
- The Administrator cannot gain request content by opening an account record.
- Sensitive mutations require recent step-up authentication.

### PA-02: Maintain the organisation

**Need:** As a Platform Administrator, I want to rename, add, move or retire teams
through proposed changes so that the hierarchy can expand safely.

**Expected behaviour**

- Current configuration is visually distinct from proposed changes.
- Search and breadcrumbs keep the selected node understandable.
- Validation reports orphaning, cycles, missing staffing and workflow metadata.
- A different authorised Administrator approves or rejects the sealed revision.
- Activation applies the approved canonical digest at the effective time.

**Acceptance checks**

- The proposer cannot approve their own change.
- Current and historical configuration cannot be edited in place.
- The organisation directory and routing choices use the activated projection.
- Existing requests retain their pinned configuration revision.

### PA-03: Manage the global classification marking

**Need:** As a Platform Administrator, I want to set the banner shown on every
page so that users see the environment's current handling marking.

**Acceptance checks**

- Allowed values are OFFICIAL, OFFICIAL-SENSITIVE, SECRET and TOP-SECRET.
- The chosen colour and text appear consistently on sign-in and protected pages.
- Changing the value requires CSRF, step-up and expected-version checks.
- The audit record contains the actor and new value, not request content.

### PA-04: Process access-assistance and account requests

**Need:** As a Platform Administrator, I want bounded notification queues for
password assistance and account requests so that I can take a governed support
action.

**Acceptance checks**

- Notifications link to the relevant safe administrative record.
- Public submissions do not disclose whether an account exists.
- Resolved requests remain attributable and cannot be processed twice.

### PA-05: See platform health without request content

**Need:** As a Platform Administrator, I want content-free service status so that
I can identify operational problems without becoming a support super-user.

**Acceptance checks**

- Health identifies dependency categories and stale worker state.
- It does not include request titles, narrative, products, cookies or tokens.
- Platform administration grants no implicit routing, production or download
  access.

## Workspace Manager and Member stories

### WS-01: Use an organisation workspace

**Need:** As a person assigned to CRIOC, a command, an Ops group or a delivery
team, I want one workspace for the unit so that its queue, people, calendar,
statistics, handover and activity are easy to find.

**Expected behaviour**

- The workspace title uses the current organisation name.
- Routing workspaces focus on queue decisions and collaboration.
- Delivery-team workspaces add board, iteration, capacity and ticket-assignment
  controls.
- Every tab explains its purpose and has loading, empty, denied and error states.

### WS-02: Maintain personal calendar activity

**Need:** As any current workspace member, I want to add leave, training, courses
and appointments so that the shared calendar reflects real availability.

**Acceptance checks**

- Manager and Member positions can create their own events.
- Personal entries are visible to current colleagues unless marked private.
- Only a delivery-team Manager can assign a calendar commitment to a ticket.

### WS-03: Maintain the roster as Manager

**Need:** As the exact-unit Manager, I want to add, transfer and end Members so
that current stewardship is clear.

**Acceptance checks**

- Manager permissions come from effective Manager membership, not profile text.
- Members cannot end another person's membership.
- Sorting defaults to Managers first and supports every column heading.

### WS-04: View a team colleague's profile

**Need:** As a current workspace user, I want to open a colleague's professional
profile and return to the People register so that I can understand who works in
the unit without losing my place.

**Acceptance checks**

- Every person name is a keyboard-accessible link to an exact-team profile.
- A clear return action opens the same team's People tab.
- The view includes professional team information but excludes service number
  and free-form personal notes.
- Exact-team access and membership history are checked on the server. An
  unrelated or inaccessible identifier reveals nothing.

### WS-05: Send a task hastener as a delivery-team Manager

**Need:** As any current Manager of the assigned delivery team, I want to send a
recorded reminder to one assigned Analyst or every Analyst assigned to the task
within my team so that follow-up is clear, targeted and accountable.

**Acceptance checks**

- The server derives eligible active Leads and Contributors from the exact-team
  request assignment. A browser-supplied recipient cannot widen that set.
- The Manager selects one eligible Analyst or all eligible Analysts and enters
  a mandatory 10 to 500 character message.
- Each recipient receives a safe notification linking to the board item.
- The request history records the Manager, resolved recipients, message and time.
- The reminder does not change ownership, assignment or Camunda workflow stage.
- Analysts, routing-unit Managers, sibling teams and Managers outside active
  production cannot send the reminder.

## Runtime operator and support stories

### OP-01: Start a local synthetic environment

**Need:** As a developer or evaluator, I want one guarded command that validates
configuration, starts dependencies, deploys BPMN and waits for readiness.

**Acceptance checks**

- Missing or placeholder secrets stop startup with a clear message.
- Ports bind to loopback by default.
- PostgreSQL, Camunda, API, worker, scanner and web health are checked.
- Mock users are refused outside an explicitly local environment.

### OP-02: Qualify a release candidate

**Need:** As a release operator, I want repeatable quality and security checks so
that a candidate is not promoted on the basis of a successful manual demo alone.

**Acceptance checks**

- Formatting, typing, lint, 95 per cent line and branch coverage, dead-code,
  terminology, documentation, licence, dependency, secret and image scans pass.
- Database migrations pass empty, upgrade, downgrade where supported, re-upgrade
  and drift checks.
- BPMN compatibility and process identity are attested.
- Open production gates remain visible and are not waived by local evidence.

### OP-03: Recover safely

**Need:** As an authorised support or recovery operator, I want documented backup,
restore and workflow-reconciliation procedures so that service can recover
without bypassing audit or access controls.

**Acceptance checks**

- Restore uses a separate target and verification before cutover.
- Reconciliation proves engine state before changing the application projection.
- Recovery diagnostics remain content-free unless a separately approved process
  grants time-bounded access.

## Cross-role scenarios

These scenarios combine several stories and are useful for acceptance testing.

### E2E-01: Standard SSG delivery

- **Given** John McGinn has an active Customer account and all required information
- **When** he submits a request, CRIOC selects JOCK, JOCK selects ACSA-B Ops,
ACSA-B Ops selects SSG Team, the SSG Manager assigns a Lead and two Contributors,
the Lead submits a managed product, the Team Manager approves it and QC releases
it
- **Then** John sees the released file or link in his dashboard, can download it and
can submit one feedback response.

The route-tracking users can follow the lifecycle but cannot approve or download
the unreleased product. Both Contributors can collaborate but cannot complete the
Lead's Camunda task.

### E2E-02: Analyst clarification

- **Given** an SSG Lead is producing a product
- **When** the Lead asks the Customer a question with a reason and deadline
- **Then** the Customer receives an exact dashboard action, the response is stored
with the request and work returns to the same Lead.

No new CRIOC, command or Ops approval is introduced.

### E2E-03: Product rework

- **Given** a Lead has submitted an immutable package revision
- **When** the Team Manager or QC Manager records changes required
- **Then** the reason is retained, production returns to the same Lead and a new
package revision is required for the next review.

The reviewed revision remains immutable and downloadable only if a later QC
release explicitly selects an approved clean artefact.

### E2E-04: Sibling branch isolation

- **Given** one request is routed through JOCK and another through SYGOC
- **When** a JOCK user opens tracking, statistics, search or a copied request URL
- **Then** only the JOCK branch is accessible. SYGOC records are absent or return a
non-enumerating denial.

CRIOC can see both branches because both are its descendants.

### E2E-05: Team staffing change during work

- **Given** a request is assigned to a current Lead and Contributors
- **When** an authorised Manager schedules a membership change
- **Then** access follows the effective membership and participant rules at the
boundary, the change is recorded, and previous assignment history remains.

A later organisation rename or move does not rewrite the request's pinned route.

### E2E-06: Camunda interruption

- **Given** an authorised person records a valid workflow outcome
- **When** Camunda becomes unavailable after ISTARI commits durable intent
- **Then** the request shows pending or support-owned failure, the outcome is not
repeated blindly, and reconciliation proves the exact engine state before the
visible projection advances.

### E2E-07: Customer cancellation

- **Given** an active request is still in a cancellable state
- **When** the owning Customer supplies a reason and confirms cancellation
- **Then** relevant users see the cancelled status, the workflow no longer offers
normal work actions, and the reason appears in history.

Another Customer, a stale page or a terminal request cannot perform the action.

### E2E-08: Private personal appointment

- **Given** a current SSG Analyst creates a personal appointment
- **When** they mark it private
- **Then** the full entry remains in their personal calendar and the SSG Team
calendar shows only `Busy` and the time.

If the same Analyst creates visible leave or training, the title and details
appear automatically in both calendars.

## Traceability

| Subject | Detailed authority |
|---|---|
| Executable human-task sequence | [Workflow and Camunda guide](architecture/WORKFLOW_AND_BPMN.md) |
| Complete organisation and synthetic users | [Organisation and routing](architecture/ORGANISATION_AND_ROUTING.md) |
| Role and permission detail | [Role and permission matrix](reference/ROLE_PERMISSION_MATRIX.md) |
| Current architecture and trust boundaries | [System architecture](architecture/SYSTEM_ARCHITECTURE.md) |
| Product acceptance specifications | [Specifications directory](specs/) |
| Security risks and controls | [Threat-model directory](threat-model/) |
| Current delivery status | [Master implementation plan](MASTER_IMPLEMENTATION_PLAN.md) |
| Dated test and browser results | [Assurance directory](assurance/) |

Automated and manual acceptance evidence should reference these story IDs rather
than duplicating the full story text in another current-state document.
