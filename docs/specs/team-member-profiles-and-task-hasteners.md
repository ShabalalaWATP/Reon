# Team member profiles and task hasteners

Status: implemented

## Purpose

This feature makes the shared team workspace more useful without turning it
into a broad people directory or an informal messaging system.

A current workspace user can select a colleague in People, view the
professional information relevant to that team and return directly to the same
People tab. A current delivery-team Manager can also send a recorded task
reminder, called a hastener, to one assigned Analyst or every Analyst currently
assigned to the request in that team.

## User stories

### View a colleague in context

As a current workspace user, I want to open a colleague's team profile and then
return to the People register so that I can understand who is working in the
unit without losing my place.

### Remind one assigned Analyst

As a delivery-team Manager, I want to send a task-specific reminder to one Lead
or Contributor so that the follow-up reaches the right person and remains part
of the request record.

### Remind the assigned delivery group

As a delivery-team Manager, I want to send the same reminder to the Lead and all
current Contributors assigned within my team so that I do not have to repeat a
message or maintain a recipient list by hand.

### Receive an accountable reminder

As an assigned Analyst, I want the reminder to appear in my notifications with
a link to the relevant board item so that I can act on it in context.

## Team profile acceptance criteria

- Each name in the People register is a keyboard-accessible link.
- The link uses the exact team and account identifiers from the authorised
  People projection.
- The profile page has a clear `Back to [team] people` action.
- Loading and failure states retain a direct route back to the same team's
  People register without depending on returned profile data.
- The profile contains name, work email, representative role, team, effective
  workspace position, membership state, rank or grade, skills and account
  status.
- The profile does not expose service number, free-form personal notes or
  information from another team.
- The server confirms that the viewer can read the exact workspace and that the
  subject has membership history in that exact workspace.
- Missing, unrelated and inaccessible records return the same not-found
  response without confirming whether the account exists.
- Loading, unavailable and inaccessible states are explicit.

## Hastener acceptance criteria

- The control appears only for a current Manager in an organisation unit of
  kind `TEAM` while the request is in active production.
- The request must be assigned to the Manager's exact team.
- Exact-team assignment and active production state are validated while holding
  the request row lock. A concurrent transition or reassignment completes first
  and the hastener then uses that resulting current state.
- Active production means `In progress`, `Customer information required` or
  `Rework required`.
- Eligible recipients are active Delivery Specialists with a current exact-team
  membership and an active Lead or Contributor assignment on the request.
- The server derives the complete recipient list. The browser cannot supply a
  wider list for the `all assigned` option.
- A named recipient must be one of the server-derived eligible recipients.
- Any current Manager of the exact delivery team can send the reminder. They do
  not need to be the Manager who originally assigned the request.
- The message is mandatory, trimmed, normalised, between 10 and 500 characters,
  and rejects control and bidirectional formatting characters. Length is
  checked after Unicode normalisation and trimming.
- A successful action appends a `task_hastener` event to the request's
  tamper-evident history, including the sender and resolved recipients.
- Each recipient receives a mandatory, content-minimised in-app notification
  with a deep link to the relevant board item. Disabling general assignment
  notifications does not suppress a direct Manager hastener.
- The action is all-or-nothing. If every resolved recipient cannot be projected
  safely, the event and partial notifications are rolled back and the Manager
  is asked to refresh.
- The board resolves a notification target through an authorised exact-request
  read independent of filters, pagination, saved views and lane visibility. An
  unavailable target produces an explicit message rather than opening an
  unrelated item.
- Sending a hastener does not claim the request, change ownership, alter the
  workflow stage, change assignments or send a command to Camunda.
- Hasteners form part of the accountable request history. Every user already
  authorised to view the request, including its Customer, can see that history.
  The notification itself remains limited to resolved assigned Analysts.
- Analysts, routing-workspace Managers, sibling teams, inactive members,
  unassigned Analysts and Managers acting after production has ended are denied.

## Accessibility and interaction

- Profile links use native link semantics and preserve a visible focus state.
- The return action is the first meaningful control on the profile page.
- The reminder editor is collapsed until requested and reports expanded state.
- Recipient and message fields have visible mandatory guidance.
- Success and failure messages use appropriate live-region roles.
- The interaction remains usable with keyboard navigation, 200 per cent zoom
  and reduced motion.

## Architecture and data

The profile is a bounded team-workspace read projection. It reuses the existing
account, organisation and effective-dated membership records but returns a
narrow contract designed for colleagues.

The hastener is an application action, not a Camunda workflow transition. The
FastAPI service authorises the Manager, resolves recipients and appends an
existing request event. The existing notification projection creates the safe
recipient notifications and treats the direct `TASK_HASTENER` event type as
mandatory. No new table or database migration is required.

The durable boundaries remain governed by:

- [ADR 0015: action projections and notification delivery](../adr/0015-action-projections-and-notification-delivery.md);
- [ADR 0025: unified organisation workspaces](../adr/0025-unified-organisation-workspaces-and-accountable-collaboration.md);
- [ADR 0028: action-oriented team workspaces](../adr/0028-action-oriented-team-workspaces.md); and
- [team-workspace threat model](../threat-model/team-workspaces-and-calendars.md).

## Required evidence

- API tests for exact-team profile access, privacy and sibling-team denial.
- Browser-component tests for profile navigation, return navigation and
  automated accessibility checks.
- API tests for all-recipient and named-recipient reminders from a second
  Manager, plus Analyst, sibling-team, unassigned-recipient and closed-stage
  denials.
- Evidence that notifications reach all and only resolved recipients even when
  general assignment notifications are disabled, and use the exact board deep
  link.
- Evidence that deep links open rework, filtered and later-page requests by
  exact identifier, or report an explicit unavailable state.
- Evidence that request status, ownership and assignment remain unchanged while
  the immutable history records the action.
- Frontend tests for a deep-linked request, all-recipient and named-recipient
  submission, success history and automated accessibility checks.
