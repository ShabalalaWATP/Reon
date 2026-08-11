# ADR 0031: consolidate team work into one workspace destination

## Status

Accepted, 11 August 2026.

## Context

The MVP exposed a role queue and a named team workspace as separate primary
destinations. The workspace then repeated queue summaries alongside planning,
handover, calendar, people, statistics and activity. This made the distinction
between "where work is done" and "where the team is managed" unnecessarily
hard to understand.

Planning and handover also introduced concepts that are not required for the
human-led request workflow. Their presence obscured the queue, assignment,
calendar and people functions that teams use most often.

## Decision

Use the named organisation workspace as the single team destination whenever a
current workspace is available. Embed the existing actionable role queue as a
unit-scoped Work queue view.

Remove Planning and Handover from the primary MVP workspace surface. Preserve
their stored server data and legacy service boundaries so that this interface
simplification is non-destructive and does not rewrite workflow history.
Remove the browser-side planning-cockpit dependency from the Board as well. The
Board continues to show the package facts it owns directly, including blockers,
dependencies, reservations and activity.

Keep standalone role queue routes for compatibility with existing deep links,
notifications and staff accounts that have no current workspace.

## Consequences

- Staff have fewer competing navigation choices.
- Queue actions remain governed by the existing server authorisation model.
- Team Managers retain Board, Calendar, People, Statistics and Activity tools.
- Advanced planning is no longer presented as part of the core MVP journey.
- Existing planning and workspace-record services may be reconsidered or
  retired separately after retention, audit and migration requirements are
  assessed.
