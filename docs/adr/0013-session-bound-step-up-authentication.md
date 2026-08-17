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
server-side opaque session and atomically rotates that session's bearer and CSRF
hashes. The browser receives the replacement bearer only as an HttpOnly cookie,
plus the expiry and replacement CSRF proof in the response. It never receives a
separate elevation bearer token and never stores the password.

The pre-confirmation bearer becomes invalid as soon as the rotation commits.
Other authenticated tabs receive only a secret-free rotation notification and
refresh `/auth/me` to adopt the browser-wide cookie's current CSRF proof. A tab
that is already anonymous is not promoted by that notification.

The FastAPI dependency checks CSRF, trusted origin, active session, Platform
Administrator role and unexpired elevation before the route handler runs. The
administration service still rechecks role and object policy in its transaction.
Failed confirmation uses the existing password verifier and bounded account
failure policy.

## Consequences

- A bearer captured before confirmation cannot inherit the resulting elevation;
  it fails authentication after the successful rotation.
- Elevation cannot be copied between sessions or replayed after session
  revocation.
- API clients must replace their CSRF proof after successful confirmation. The
  API and browser client must therefore be deployed together for this additive
  response contract.
- Read-only account and organisation metadata remains usable without repeated
  confirmation.
- A future federated identity provider should replace local password
  confirmation with an identity-provider `max_age` or approved equivalent while
  retaining the server-side action gate.
