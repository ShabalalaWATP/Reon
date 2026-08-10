# ADR 0025: Unified organisation workspaces and accountable collaboration

## Status

Accepted, 9 August 2026.

## Context

Delivery teams have effective-dated membership and collaboration tools, while
routing units use a simpler membership list and lack shared calendars, rosters
and activity. Service requests also store one assigned specialist even though a
delivery team may need several Analysts to contribute. Camunda user tasks still
require one accountable assignee.

Maintaining separate workspace models would duplicate access, expiry, transfer,
notification and audit rules. Treating several Analysts as simultaneous Camunda
assignees would make one workflow outcome ambiguous.

## Decision

Use one effective-dated organisation membership model for every unit kind. Add
an independent workspace position of Manager or Member and calculate workspace
capabilities on the server from unit kind, global role, membership and explicit
management authority.

Present People as one sortable membership-history ledger across all unit kinds.
The default order places current Managers before Members; every column exposes
an accessible two-direction sort. Roster writes require the Manager position as
well as explicit authority, so a grant alone cannot promote a regular user into
local administration.

Represent request collaboration as one active Lead and zero to ten active
Contributors. Only the Lead is the Camunda assignee. Contributors receive
application-level collaboration access, while linked work packages remain the
unit of parallel delivery work. Use durable commands for Lead handover.

Allow every active member to manage self-owned calendar events. Only exact-unit
Managers can create team events or assign ticket-linked commitments to other
people. Routing Managers receive staffing and oversight powers but no task
allocation or approval stage.

## Consequences

- Existing routing and team memberships require a controlled data migration.
- Authorisation becomes consistent across calendars, people, statistics and
  workspace activity.
- Routing and delivery workspaces share a shell but retain different tools.
- Multi-Analyst collaboration is explicit without weakening Camunda authority.
- A later external calendar connector can consume the same redacted canonical
  events without becoming authoritative.
