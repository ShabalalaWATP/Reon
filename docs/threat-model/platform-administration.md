# Platform Administration Threat Model

## Scope and assets

This model covers the local/test account register, profile and membership edits,
activation state, session revocation, organisation display-name changes, derived
team staffing and administrative audit. Service requests, products, workflow
tasks and Customer feedback are explicitly outside the administration data path.

The shared `admin` password and Scottish-football display names are synthetic MVP
fixtures. Demo seeding and the administration surface are forbidden outside
local/test configuration.

## Trust boundaries

```text
Administrator browser -> React admin workspace -> FastAPI admin routes
                                             -> PostgreSQL metadata and audit

Service-request repositories and Camunda are not administration dependencies.
```

## Threats and controls

| Threat | Control |
| --- | --- |
| A non-administrator calls an admin endpoint | Require an active `PLATFORM_ADMIN` at the route and final service boundary; return a non-disclosing denial |
| An administrator uses the role to read request content | Use dedicated metadata schemas, repositories and navigation; retain explicit denial in every request, tracking, task and product policy |
| Cross-site request forgery changes an account | Require the session-bound CSRF header and trusted origin on every mutation |
| A crafted role or membership bypasses scope | Accept enum roles and UUIDs only; validate role-to-unit-kind compatibility and exact membership cardinality in FastAPI |
| Concurrent edits silently overwrite one another | Require `expectedVersion`, lock the target and return `409` for stale mutations |
| An administrator locks out all administration | Reject self-deactivation and removal of the last active Platform Administrator |
| A deactivated user retains access | Increment credential state and revoke every active session within the account mutation transaction |
| A user with active work is moved or deactivated | Reject security-affecting changes while the user owns a claimed or pending task; require workflow reassignment first |
| Deletion breaks historical attribution | Expose deactivation and reactivation only; keep stable user IDs and immutable usernames |
| Organisation rename breaks routing | Change display name only; keep UUID, code, parent and Camunda candidate groups immutable; update denormalised display projections transactionally |
| Duplicate or misleading organisation names | Trim and length-limit names and require uniqueness amongst direct siblings |
| Staffing display drifts from access reality | Recalculate from active, role-qualified Manager and Analyst memberships after relevant mutations; preserve the derived result on reseed |
| Sequential username allocation races | Allocate the next `adminN` under a database lock and retain a unique constraint as the final guard |
| Administrative history is altered | Append canonical, prior-hash-linked audit events containing actor, target, action and metadata-only before/after state |
| Password appears in the browser or logs | Read the local fixture password from server configuration, hash with Argon2id off the async event loop, never return it and redact credentials from logs |
| Weak fixture credentials escape the MVP | Refuse demo users and administration routes outside local/test; replace with approved federated identity before pilot deployment |

## Required evidence

- Administrator and non-administrator list, detail and mutation tests.
- Explicit administrator denials for request, tracker, work-item and product APIs.
- CSRF, inactive-account, unknown-ID and malformed-membership tests.
- Self-deactivation, last-administrator and active-work conflict tests.
- Stale version and competing username-allocation tests.
- Session revocation and subsequent authentication denial tests.
- Rename uniqueness, stable-code, routing-group and hierarchy-preservation tests.
- Staffing transitions for last Manager and last Analyst, including reseed safety.
- Audit-chain verification and assertions that request content and credentials are
  absent from administrative events.
- Production-mode denial and local-only password handling tests.
- Frontend route, loading, empty, error, keyboard and WCAG checks.

## Residual risks and exit gates

- One shared weak password prevents individual credential assurance. It is
  accepted only for an isolated synthetic local/test MVP.
- Sequential usernames are intentionally discoverable and require no secrecy.
- Local database roles do not yet provide an independent append-only enforcement
  layer for the admin audit table.
- Before any pilot or production use, replace demo authentication with approved
  identity, privileged-access, joiner/mover/leaver and recovery processes.
- Production requires restricted database grants, audit monitoring, backup and
  restore evidence, dependency and secret scanning, and authorised staging DAST.
