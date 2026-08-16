# Unified Organisation Workspaces

## Purpose

Provide every staffed organisation unit with a useful shared workspace while
preserving the difference between human-led routing functions and delivery
teams. Every active member can maintain their own calendar availability.
Managers receive bounded local administration. Delivery Managers may assign one
Lead Analyst and several Contributors to a service request. Routing Managers do
not assign routing work: an eligible user claims the Camunda task and records
the routing decision themselves.

## Workspace shape

| Unit kind | Required views | Manager-only controls |
| --- | --- | --- |
| JIOC root | Overview, Work queue, Calendar, People, Statistics, Activity | Membership and team events |
| Command | Overview, Work queue, Calendar, People, Statistics, Activity | Membership and team events |
| Ops group | Overview, Work queue, Calendar, People, Statistics, Activity | Membership and team events |
| Delivery team | Overview, Work queue, Board, Calendar, People, Statistics, Activity | Membership, request assignment, commitments and WIP |

The server returns capabilities for the selected unit. React does not infer
authority from a role name, navigation item or organisation kind.

The account menu and personal profile must present the representative workflow
role and the effective workspace position as separate facts. For example, a
JIOC Manager is a `JIOC Routing User` by representative role and a `Manager` in
the JIOC workspace. The compact account identity combines both labels, while
the expanded profile names the organisation attached to each position. Neither
label is an authorisation source.

## Membership and management

One effective-dated organisation membership is authoritative for workspace
access. A membership identifies an organisation unit and a workspace position
of `MANAGER` or `MEMBER`. It records its effective window, optimistic version,
the actors and reasons that started or ended it, and projection timestamps.

Managers may add an existing compatible account, schedule a transfer and end a
Member assignment in their exact unit. They cannot create accounts, change a
global role, deactivate an account, appoint or remove another Manager, or cross
a parent or sibling boundary. Platform Administrators retain those powers.

The People register is a sortable operational ledger. Every visible column can
be sorted in either direction, with an accessible sort state and deterministic
tie-breaking. Its initial order places Managers first, then Members, while
retaining current, scheduled and ended history. Roster controls are available
only when the authenticated person has both a current `MANAGER` membership in
the exact unit and its active exact-unit `ROSTER` grant. React hides those
controls for Members, but FastAPI independently enforces the same rule for every
roster mutation.

An active delivery assignment, capacity reservation or ticket leadership must
be handed over before membership can end. All changes are immutable activity.

## Calendar

Every current Manager and Member may create, edit and cancel their own Leave,
Course or training, Duty, Appointment, Availability, Service work and Other
events from either the personal calendar or their shared workspace calendar.
The self-service API always derives the subject from the authenticated session.
It cannot accept another user, request or work-package identifier.

Managers may additionally create unit events and ticket-linked commitments for
one or more current members. A linked commitment is valid only when the request
or work package belongs to the Manager's exact delivery team. Routing Managers
may create team events but cannot create ticket commitments.

Personal events default to showing their title, category and notes to the
member's current exact unit. The creation form provides one unchecked `Private
appointment` control; selecting it redacts the title and notes before a shared
response leaves the backend and shows colleagues only `Busy` and the event time.
New availability-only personal events are not accepted, while existing records
retain that projection. Existing events are clickable and empty calendar slots
support keyboard-accessible quick creation. A single prominent Add event button
and every calendar-slot creation affordance open the same modal form. Selecting
a day pre-fills that date, successful creation closes the modal and returns
focus, and validation or API errors preserve entered values. Dragging is an
enhancement to the same commands, never a separate authority path.

## Multiple Analysts on one request

A delivery request has exactly one active Lead Analyst and up to ten additional
assigned Analysts. Every participant must be a current member of the assigned
team. The Lead is the accountable Camunda assignee, while every assigned Analyst
has the same production controls through the application policy boundary.

Managers assign the Lead and additional Analysts atomically with an optimistic
request version and mandatory reason. Assignment changes retain history and
dispatch a durable Camunda assignment command. Concurrent changes have one
winner.

## Routing workspaces

JIOC, Command and Ops work remains claim-based. A routing Manager has the same
routing action as a Member only after personally claiming the relevant task.
Manager status adds staffing, calendar, metadata and oversight powers, not an
approval gate or authority to allocate a routing decision to someone else.

Queue measures are content-free: unclaimed, claimed, information required,
oldest age, median routing duration and direct-child distribution. Delivery
workspaces instead show demand, status, due risk, throughput, Manager review,
capacity and release measures. Individual performance ranking is prohibited.

## Authoritative operational records

Requests, structured conversations, product packages, Work Package cards and
Camunda remain the authoritative operational records for their named concerns.
No supporting board or calendar mutation may advance workflow implicitly.

## Security and acceptance

- Authorise every read and write by active membership, exact unit and action.
- Require current exact-unit Manager position as well as the roster action for
  add, transfer, eligible-person and end-membership operations.
- Deny parent, sibling, expired, revoked and cross-unit access without revealing
  object existence.
- Use CSRF protection, optimistic versions, mandatory reasons and immutable
  activity for every mutation.
- Redact private calendar content in the repository response boundary.
- Remove participant and membership access immediately from protected caches.
- Dispatch Camunda changes through the existing durable outbox and fenced worker.
- Notify only authorised current recipients with content-free summaries.
- Maintain at least 95 per cent line and branch coverage independently in the
  backend and frontend, including negative authorisation and concurrency tests.
- Verify every People column sort in both directions, Manager-first initial
  ordering, Member read-only behaviour, Add event modal focus and day pre-fill.
- Verify that Manager and Member accounts see their effective workspace
  position alongside, rather than hidden behind, their representative role.
