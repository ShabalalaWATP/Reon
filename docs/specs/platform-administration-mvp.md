# Platform Administration MVP

## Outcome

Give a synthetic Platform Administrator a bounded workspace for maintaining MVP
accounts and organisation labels without granting service-request content access.
Every configured delivery team starts with at least one Team Manager and one Team
Analyst. SSG Team starts with three Managers and seven Analysts.

## Local identity convention

- Seeded logons are sequential `admin1`, `admin2`, `admin3` and so on.
- The shared synthetic password is `admin` in local and test only.
- Production configuration continues to reject demo users and weak local settings.
- Existing seeded accounts are renamed in place so request, audit and assignment
  references retain the same user identifiers.
- New administrator-created MVP accounts receive the next available `adminN`
  username and the configured local demo password.

## Administrator authority

The Platform Administrator may:

- list and search synthetic account metadata;
- create a user, edit display name, role, scope and organisation memberships;
- deactivate or reactivate access;
- browse the complete organisation;
- rename configured organisation units while stable IDs, codes and Camunda groups
  remain unchanged.

The Platform Administrator may not:

- list, open, search, route, approve or disseminate service requests;
- hard-delete an identity or its audit history;
- edit stable organisation codes, candidate groups, hierarchy or workflow state;
- use these local administration endpoints outside local/test demo mode.

CRIOC Routing Users continue to accept and triage Customer service requests.

## Validation and security rules

- Every mutation requires an authenticated Platform Administrator and CSRF token.
- Every mutation also requires the Administrator to confirm their current
  password. Successful confirmation elevates only the current opaque session for
  five minutes; the browser receives the expiry time, not a reusable elevation
  token.
- FastAPI checks the unexpired elevation before the route handler. Expired or
  missing elevation returns `STEP_UP_REQUIRED`, regardless of UI state.
- Failed confirmation uses the existing generic authentication response and
  bounded failure controls. A locked account invalidates existing sessions.
- Elevation ends at expiry, logout, session revocation, account deactivation or
  credential-version change.
- Object identifiers are loaded and checked server-side.
- Role and organisation-kind compatibility is authoritative in FastAPI.
- A deactivated user loses all current sessions and cannot claim future work.
- Usernames are server-generated and immutable.
- Organisation names are trimmed, length-bounded and unique amongst siblings.
- Removing a user means reversible deactivation, never destructive deletion.
- Team staffing is recalculated from active Manager and Analyst memberships.
- Account and organisation mutations create tamper-evident administrative audit
  events without copying request content.

## Frontend direction

Visual thesis: a calm graphite control surface with one cyan action hierarchy,
dense account rows and a restrained metadata inspector.

Content plan: account search and status first, selected profile editor second,
organisation naming and staffing context third.

Interaction thesis: fast row selection, a compact inline status transition and
clear save confirmation, all disabled when reduced motion is requested.

The page uses the existing navigation rail, typography, dividers and form
controls. It avoids a generic card dashboard and exposes one primary action at a
time.

## Acceptance

- All active seeded accounts authenticate with their documented sequential
  username and local password; inactive accounts remain denied.
- All 27 delivery teams have an active Manager and Analyst.
- SSG Team has three active Managers and seven active Analysts.
- An Administrator can create, edit, deactivate and reactivate a user.
- Every administration mutation is denied before password confirmation and
  succeeds only during the five-minute elevation window.
- Another session cannot reuse an Administrator's elevation, and password or
  elevation state never enters logs or audit summaries.
- An Administrator can rename a team and see the new name across organisation and
  routing views without changing its stable workflow identity.
- Non-administrators and non-local configurations cannot use administration APIs.
- Administrator request list and detail access remains denied.
- Backend and frontend line and branch coverage remain at least 95 per cent.
