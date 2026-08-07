# ADR 0013: Session-Bound Step-Up Authentication

## Status

Accepted locally for the MVP.

## Context

Platform administration changes identity and access metadata. An ordinary
signed-in browser session provides insufficient protection when a device is
left unattended or a session is replayed.

## Decision

Require password confirmation before every class of administration mutation.
Successful confirmation sets a five-minute `elevated_until` value on the current
server-side opaque session. The browser receives the expiry time only. It never
receives an elevation bearer token and never stores the password.

The FastAPI dependency checks CSRF, trusted origin, active session, Platform
Administrator role and unexpired elevation before the route handler runs. The
administration service still rechecks role and object policy in its transaction.
Failed confirmation uses the existing password verifier and bounded account
failure policy.

## Consequences

- Elevation cannot be copied between sessions or replayed after session
  revocation.
- Read-only account and organisation metadata remains usable without repeated
  confirmation.
- A future federated identity provider should replace local password
  confirmation with an identity-provider `max_age` or approved equivalent while
  retaining the server-side action gate.
