# Structured Service Request MVP

## Status

Approved as the pilot-MVP scope, 6 August 2026. The initial vertical slice is an
implementation milestone, not completion of every capability in this spec.

## Objective

Create a deliberately limited second ISTARI product that retains the established
login and application-shell design while replacing conversational intake with a
structured form and the representative routing and delivery language agreed for
this MVP.

The MVP must let a Customer submit, follow and complete a service request. Every
routing, assignment, review and dissemination choice is made by a named person through
an executable Camunda workflow.

It must also support save-and-resume drafts, recorded manual checks for duplicate
or related records, time-stamped operational notes, workload visibility and a
supporting Platform Administrator. These additions remain human-led and must not
create broad access to request content.

## Visual thesis

A calm, precise service workspace built from graphite surfaces, disciplined cyan
accents, mono request references and clear stage hierarchy, retaining ISTARI's
recognisable character without defence, artificial-assistant or command-centre
language.

## Content plan

1. Login: ISTARI brand, neutral value points and account access.
2. My requests: status summary, active request register and one submission action.
3. Request form: the need, outcome, deadline, context and delivery expectations.
4. Request workspace: overview, current owner, activity, service product and feedback.
5. Staff work: one role-filtered queue with request context and human actions.
6. Administration: identity, role, team and safe reference-data maintenance with
   no implicit access to requests.

## Interaction thesis

- The login brand and access panel enter as one restrained sequence, with a slow
  logo float and lightweight ambient particles.
- Selected navigation, queue rows and request status transition with a short,
  shared cyan indicator rather than decorative card motion.
- The workflow journey reveals completed stages and pulses only the current
  stage. All motion respects `prefers-reduced-motion`.

## Representative users

| Role | Objective | MVP activity | Value |
| --- | --- | --- | --- |
| Customer | Receive a timely response | Submit, track, download and give feedback | Complete requests and visible progress |
| JIOC Routing User | Understand and direct incoming demand | Review, categorise, request information or select a command | One source of truth and less administration |
| Command Routing User | Direct work to the appropriate Ops group | Hold, resume, track and select a direct Ops group | Visible demand, ownership and progress |
| Ops Routing User | Direct work to the appropriate team | Select any direct team and track progress | Clear demand and workload ownership |
| Team Manager | Assign and oversee delivery | Assign Analysts and check their service product | One view of origin, ownership and delivery |
| Team Analyst | Produce the service product | Manage assigned work and submit the product | Visible workload, status and history |
| QC Manager | Assure and disseminate completed work | Review, return, approve and disseminate | Clear readiness, approval and delivery |

The Platform Administrator is a supporting technical role, not an eighth workflow
decision-maker. It manages identities, roles, teams and safe configuration
metadata, and cannot browse request content by default.

## Synthetic user fixtures

The local/test seed contains 73 Scottish-football display names. Logons are
`admin1` through `admin99`, with the local-only shared password `admin`.
Every team has at least one Manager and one Analyst. OSG has three Managers and
seven Analysts. The complete traceable roster is maintained in
`docs/architecture/ORGANISATION_AND_ROUTING.md`.

## Form contract

Required fields:

- request title;
- description of the need;
- specific question to answer;
- desired outcome;
- background and known context;
- subject area or location;
- relevant period start and end;
- Customer urgency;
- activity, project or decision supported;
- required-by date and why it matters;
- preferred deliverable type;
- success criteria;
- constraints or caveats;
- supporting information available;
- sensitivity and handling instructions.

The Customer does not select an internal business area, recipient, delivery team
or Analyst. The submit control remains disabled until client validation succeeds.
Matching Pydantic validation is authoritative. Submitted revisions are
immutable and all later information is appended to the activity history. Before
submission, only the originating Customer may update or delete a draft. Drafts do
not start a workflow instance.

During intake, authorised staff may search records already held by this MVP and
record a possible duplicate, related request or existing output link. Matching and
the decision to progress remain manual. Search results are filtered by the same
scope policy as all other data access.

Binary attachments are outside this MVP. Team Analysts submit a titled plain-text
service product. Controlled file handling requires a separate specification
covering quarantine, malware scanning, magic-byte validation, immutable versions
and download authorisation.

## Human-led workflow

```text
Submit request
  -> JIOC routing
     -> Information required -> Customer response -> JIOC routing
     -> Closed without delivery
     -> Select command
        -> Command routing
           -> On hold -> Command routing
           -> Return to JIOC
           -> Select direct Ops group
              -> Ops routing
                 -> Return to command routing
                 -> Select direct team
                    -> Team Manager assignment
                       -> Return to Ops routing
                       -> Analyst product development
                       -> Team Manager review
                          -> Changes required -> Analyst product development
                          -> QC review
                             -> Changes required -> Analyst product development
                             -> Ready for dissemination
                             -> Disseminate -> Customer download -> Completed
```

All gateway variables are supplied by the named user completing the preceding
task. Camunda must not infer or recommend a route.

## Status projection

`ROUTING_PENDING`, `TRIAGE_REVIEW`, `INFORMATION_REQUIRED`,
`COORDINATION_REVIEW`, `ON_HOLD`, `ALLOCATION_REVIEW`, `DELIVERY_PLANNING`,
`IN_PROGRESS`, `LEAD_REVIEW`, `REWORK_REQUIRED`, `QUALITY_REVIEW`,
`READY_FOR_RELEASE`, `COMPLETED`, `CLOSED_NOT_PROGRESSED` and `CANCELLED`.

The Customer dashboard groups these into Needs your input, In progress and
Completed without exposing engine terminology.

JIOC, Command Routing and Ops Routing Users retain a separate route-scoped,
read-only tracker after their routing action. It shows title, reference,
ownership and lifecycle and permits an exact-route member to reopen the original
submitted request. It excludes actions, clarification, feedback and product
content or links. These users do not approve the service product and cannot use
tracking access to open unreleased content. The detailed amendment and acceptance
criteria are in `tracking-lifecycle-and-analytical-visuals.md`.

## Pages and routes

- `/login`
- `/requests`
- `/requests/new`
- `/requests/:requestId`
- `/triage`
- `/coordination`
- `/allocation`
- `/delivery/team`
- `/delivery/my-work`
- `/quality-release`
- `/organisation`
- `/tracking`
- `/administration`

All staff work routes may share one queue component, but backend permissions and
query scope remain role-specific.

## Acceptance criteria

- The new repository exists outside the Coeus directory and Coeus is unchanged.
- Login preserves the ISTARI composition with neutral copy and accessible motion.
- A Customer can submit the complete form and view only their requests.
- A Customer can save and resume a private draft without starting Camunda.
- Each representative role sees only its applicable queue and actions.
- Staff can append attributable notes, and permitted leads can see scoped workload.
- Intake can record manual duplicate or related-work checks without automated
  recommendations or cross-scope data exposure.
- Every route-affecting choice is a human-completed Camunda user task.
- Every configured command, Ops group and team is a first-class selectable
  destination for the applicable routing user, with no demonstration-only choice.
- Every seeded team has its own active Manager and Analyst membership. A later
  administrative change may make it unstaffed, which shows `Awaiting staffing`
  and never assigns OSG users.
- OSG is the initial operational team, with additional Manager and Analyst users.
- A Platform Administrator can provision, edit, deactivate and reactivate users
  and rename organisation display names without accessing request content.
- Camunda 8.9.14 is pinned locally and accessed only through FastAPI.
- PostgreSQL 17 stores application state; Camunda uses separate owned storage.
- A disseminated plain-text service product is downloadable only by the
  originating Customer through an authenticated application-owned endpoint.
- Feedback can be submitted once and only after successful completion.
- Object-level authorisation, CSRF, session expiry and disabled-account behaviour
  are covered by tests.
- Cross-role, cross-scope, direct-identifier and invalid-transition cases are
  covered by API tests, including denial of request content to administrators.
- Audit records are append-only and hash-chained; integrity verification detects
  modification.
- Backend and frontend line and branch coverage each meet 95 per cent.
- Representative journeys meet WCAG 2.2 AA, and ordinary pages and API operations
  meet p95 below two seconds at agreed pilot load.
- Structured logs exclude request bodies and secrets; backup and restore evidence
  is required before pilot exit.
- Static checks reject legacy application vocabulary and files over 350 lines.
- No secrets or non-synthetic operational content are committed.

## Explicit exclusions

Chat, voice, LLMs, automated routing, recommendations, shared product search,
binary files, dynamic process editing, external messaging, calendars, capacity
optimisation, broad organisation administration, production deployment and
production identity federation.
