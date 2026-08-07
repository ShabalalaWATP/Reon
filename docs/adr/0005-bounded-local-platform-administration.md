# ADR 0005: Bounded Local Platform Administration

## Status

Accepted for the synthetic MVP.

## Context

The expanded organisation needs staffed workflow destinations and a way to
maintain fictional accounts and labels during testing. Hard deletion would break
historical attribution, while allowing support users to read service content
would create an unnecessary universal-access role.

## Decision

- Keep account and organisation administration in PostgreSQL behind dedicated
  FastAPI services and Platform Administrator routes.
- Enable the MVP administration surface only when demo users are enabled in a
  local or test environment.
- Generate sequential `adminN` usernames server-side and use the configured demo
  password for local synthetic accounts.
- Treat user removal as deactivation and revoke sessions atomically.
- Permit edits to display name, role, scope and governed memberships.
- Permit organisation display-name edits only. Stable IDs, codes, hierarchy and
  candidate groups remain immutable.
- Recalculate delivery-team staffing from active Manager and Analyst membership.
- Keep the Platform Administrator outside every service-request content policy.

## Consequences

The MVP can demonstrate every team queue with real candidate members and can be
maintained without database scripts. Historical actors remain intact. The shared
password and local account lifecycle are explicitly unsuitable for production,
where federated identity and approved privileged-access controls replace this
surface.
