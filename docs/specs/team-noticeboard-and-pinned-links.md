# Team noticeboard and pinned links

Date: 13 August 2026. Status: implemented.

## Purpose

Give every organisation workspace a small shared surface on its Overview:
standing notices (handover-style information that stays true until archived)
and pinned links to useful references. Both were requested to support shift
handover and day-to-day orientation without adding another workspace tab.

## Decision: reuse workspace collaboration records

The backend already provides bounded, audited workspace records
(`/api/v1/team-workspaces/{unitId}/records`, migration
`0027_workspace_collaboration`) with kinds DESCRIPTION, HANDOVER, RISK,
BLOCKER, DECISION and LINK, an OPEN or RESOLVED status, canonical public-HTTPS
URL validation for links, optimistic versioning and immutable
`workspace_record_events`. No backend change is made for this feature.

- The noticeboard lists every OPEN record that is not a LINK, newest first,
  with its kind shown as a pill. Posting from the panel creates a HANDOVER
  record labelled "Notice" in the interface.
- Pinned links list OPEN LINK records. The stored URL is already canonicalised
  and restricted to public HTTPS destinations by the API.
- Archiving or removing uses the existing resolve action and therefore
  requires a reason of at least ten characters, kept with the record.

## Authority model

Unchanged from workspace collaboration: anyone with workspace access (current
membership or a live management grant) can read. Posting and resolving require
the caller's `grantId` to resolve to a ROSTER management grant on the exact
unit, enforced server side. The interface shows the forms and archive controls
only when the current access carries ROSTER permission, and states plainly for
members that Managers keep the board current. Hiding the controls is a
presentation choice, not the authorisation control.

## Interface

`TeamNoticeboard` renders on the workspace Overview for both delivery and
routing units, between the team home panels and the statistics strip. It uses
the existing `workspace-records`, `workspace-collaboration` and
`workspace-record` styles: notices in the main column, links in the side
column, with disclosure-style "Post a notice" and "Add a link" forms for
Managers. List, create and resolve responses all return the fresh record list,
which replaces the cached query directly. A failed load reports "Noticeboard
unavailable" inline without hiding the rest of the Overview.

## Test coverage

`TeamNoticeboard.test.tsx` covers Manager posting (asserting the HANDOVER and
LINK request bodies including `grantId`), archiving with the recorded reason
and `expectedVersion`, resolved records staying hidden, the read-only member
view, the unavailable state and an axe accessibility pass of the Overview.
