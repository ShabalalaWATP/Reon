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
| JIOC root | Overview, Queue, Calendar, People, Statistics, Handover, Activity | Membership, team events, workspace metadata |
| Command | Overview, Queue, Calendar, People, Statistics, Handover, Activity | Membership, team events, workspace metadata |
| Ops group | Overview, Queue, Calendar, People, Statistics, Handover, Activity | Membership, team events, workspace metadata |
| Delivery team | Overview, Board, Calendar, People, Planning, Statistics, Activity | Membership, request assignment, commitments, WIP and capacity |

The server returns capabilities for the selected unit. React does not infer
authority from a role name, navigation item or organisation kind.

## Membership and management

One effective-dated organisation membership is authoritative for workspace
access. A membership identifies an organisation unit and a workspace position
of `MANAGER` or `MEMBER`. It records its effective window, optimistic version,
the actors and reasons that started or ended it, and projection timestamps.

Managers may add an existing compatible account, schedule a transfer and end a
Member assignment in their exact unit. They cannot create accounts, change a
global role, deactivate an account, appoint or remove another Manager, or cross
a parent or sibling boundary. Platform Administrators retain those powers.

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

Leave and appointments default to availability-only. Private notes are redacted
before a shared response leaves the backend. Existing events are clickable and
empty calendar slots support keyboard-accessible quick creation. Dragging is an
enhancement to the same commands, never a separate authority path.

## Multiple Analysts on one request

A delivery request has exactly one active Lead Analyst and up to ten active
Contributors. Every participant must be a current member of the assigned team.
The Lead is the sole Camunda assignee and performs workflow-stage outcomes.
Contributors may read the authorised request, collaborate on linked work
packages and draft artefacts, and receive safe notifications, but cannot
complete the Lead's Camunda task.

Managers assign the Lead and Contributors atomically with an optimistic request
version and mandatory reason. Handover promotes a current Contributor or another
eligible Analyst to Lead, retains history and dispatches a durable Camunda
assignment command. Concurrent changes have one winner. Existing single
assignments are backfilled as Lead participation.

## Routing workspaces

JIOC, Command and Ops work remains claim-based. A routing Manager has the same
routing action as a Member only after personally claiming the relevant task.
Manager status adds staffing, calendar, metadata and oversight powers, not an
approval gate or authority to allocate a routing decision to someone else.

Queue measures are content-free: unclaimed, claimed, information required,
oldest age, median routing duration and direct-child distribution. Delivery
workspaces instead show demand, status, due risk, throughput, Manager review,
capacity and release measures. Individual performance ranking is prohibited.

## Collaboration

Managers may maintain a bounded workspace description, contact text, useful
HTTPS links, handover notes, risks, blockers and decisions. This is not chat, a
document store or a second workflow. Requests, products and Camunda remain the
authoritative operational records.

## Security and acceptance

- Authorise every read and write by active membership, exact unit and action.
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
