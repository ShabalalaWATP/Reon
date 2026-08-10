# ADR 0008: Canonical Workforce Calendars

## Status

Accepted.

## Context

Teams need personal and shared calendars, commitments and capacity signals.
Copied team absence records drift, leak private text and make transfers difficult.
The existing Coeus behaviour provides a useful contract, but ISTARI Service needs
an independent, smaller implementation aligned with its own permissions and
terminology.

## Decision

- Store one canonical event or recurring series in PostgreSQL with owner, time
  zone, visibility, activity, recurrence, version and lifecycle state.
- Support all-day and timed events, validated IANA zones, and constrained daily
  or weekly recurrence. Bound every recurrence expansion by requested date range.
- Represent occurrence exceptions and future-series splits explicitly. Never
  rewrite historical occurrences.
- Derive personal and authorised exact-team projections at query time from
  canonical data, current memberships and active grants. Higher organisational
  levels receive aggregate statistics, not individual calendar records.
- Visibility is private, availability-only or team-detail. Shared projections
  redact title and notes before leaving the repository boundary.
- Permit Managers with the calendar action to create team events and personal
  commitments. The subject acknowledges or disputes a commitment with a
  mandatory reason.
- Calculate capacity from canonical calendar periods and work reservations using
  a versioned preview and commit token.
- Use one accessible modal creation surface for the toolbar and day-slot entry
  points. Day selection pre-fills the date, errors retain context, successful
  creation closes the surface and focus returns to the invoking control.
- Keep external calendar connectors out of scope until separately specified and
  threat-modelled.

## Consequences

One event and one creation interaction remain consistent across views and
organisation changes. Privacy and capacity logic have one source. Exact-team
calendar scope reduces unnecessary availability exposure. Recurrence,
daylight-saving changes, transfers and concurrent edits require property and
boundary tests.

## Rejected alternatives

- Copy events into every team calendar: creates drift and deletion ambiguity.
- Store rendered occurrences only: loses series intent and makes future edits
  unsafe.
- Integrate Exchange or Google Calendar in the MVP: introduces credentials,
  external sharing and reconciliation risk before the local model is proven.
