# ADR 0011: Effective-dated Team Membership

## Status

Accepted, 7 August 2026.

## Context

Every operational team has named Managers and Analysts. Team Managers need to
add existing Analysts, end membership and schedule transfers, while account
creation, deactivation and role changes remain Platform Administrator duties.
The current-team fields on an account are insufficient because they erase
history and make concurrent or future-dated moves ambiguous.

Membership also controls request visibility, staffing state and the team
workspace. A stale or cross-team mutation must not create two effective home
teams, silently abandon active work or widen access.

## Decision

Use an effective-dated `team_memberships` aggregate as the source of truth for
team history. Keep the existing account team fields and organisation membership
rows as a compatibility projection of the one membership effective now.

- Lock the subject account before any membership mutation.
- Permit roster queries and mutations only when the actor has both a current
  exact-team `MANAGER` membership and an active exact-team `ROSTER` grant. This
  defence-in-depth rule rejects stale or manually misconfigured Member grants.
- Accept existing, active Analysts only. Identity and role management stay in
  the Platform Administrator service.
- Require a bounded reason and expected version for every end or transfer.
- Represent a scheduled transfer as a finite source membership and one future
  destination membership. A partial unique constraint permits only one open
  membership for a person.
- Reject removal or transfer while the Analyst owns active service work.
  Later package, commitment and reservation aggregates must join the same
  disposition guard before their features can be considered complete.
- Apply due scheduled changes through an idempotent synchronisation service,
  update the compatibility projection, revoke sessions whose scope changed and
  append immutable metadata activity.
- Return end reasons to exact-team Managers only. Analysts can see roster dates
  and states, but not management evidence.

## Consequences

Historic attribution survives transfers and deactivation. Scheduled moves have
one database-backed winner and stale clients receive a conflict. Existing work
and routing code continues to consume a current-team projection while new code
uses the timeline.

The synchronisation service must run at every safe application boundary until a
dedicated scheduler is introduced. Package, calendar commitment and capacity
reservation guards remain explicit prerequisites of their later phases.

## Evidence

Migration `0006_team_memberships`, exact and cross-team API tests, scheduled
one-winner and activation tests, active-work blocking tests, Administrator
timeline-alignment tests, a misconfigured-Member-grant denial and the sortable
team People workspace.
