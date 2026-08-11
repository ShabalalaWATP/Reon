# ADR 0026: Global classification and password assistance

Status: accepted, 10 August 2026.

## Context

The MVP needs a visible platform marking and a way for a user who cannot sign in
to alert support. The current user record has no email. Returning an account
lookup result or implementing an unverified self-service password reset would
create account-enumeration and credential-takeover risks. A classification mark
kept only in React would diverge between users and disappear on restart.

## Decision

Add a unique managed email to the user identity and preserve the reviewed work
email when an account request is approved. Store a singleton, versioned global
classification record in PostgreSQL, expose a content-minimised public read and
require an elevated Platform Administrator for optimistic mutation. Record each
change in the existing tamper-evident administration audit chain.
Persist each classification by its declared public string value so the ORM and
migration-owned constraint cannot diverge where a Python member name differs.

Implement forgotten password as assistance rather than password reset. The
public endpoint always returns the same accepted result. It records a bounded,
content-minimised attempt, matches only active users and publishes an existing
mandatory account-security notification to active Platform Administrators. The
submitted email is not copied into the attempt or notification.

Keep PostgreSQL authoritative for both settings and assistance attempts. React
continues to call FastAPI only. Camunda has no part in identity assistance or
classification presentation.

## Consequences

- The MVP gains an attributable, durable and globally consistent mark.
- Administrators receive assistance alerts inside their existing notification
  centre without introducing an email provider or reset-token lifecycle.
- A visible platform marking cannot be mistaken for request-level handling
  enforcement; the interface and documentation state this boundary explicitly.
- Connected deployment still requires enterprise identity recovery, verified
  contact ownership and approved security support procedures.
- The public endpoint requires rate and retention controls because identical
  responses prevent enumeration but do not alone prevent flooding.

## Rejected alternatives

- Returning `email not found`, because it enumerates accounts.
- Sending or displaying the MVP shared password, because that would expose a
  credential and provide no identity verification.
- Browser-local classification, because it is neither global nor auditable.
- Per-request classification in this change, because request sensitivity already
  has a separate business meaning and must not silently inherit a platform label.
