# Platform Administration Threat Model

## Scope and assets

This model covers the local/test account register, profile and membership edits,
activation state, session revocation, organisation display-name changes, derived
team staffing, effective-dated organisation and workflow configuration versions,
approved product-domain policy, configuration approvals and administrative
audit. Service requests, product content, workflow tasks and Customer feedback
are explicitly outside the administration data path.

The shared `admin` password and Scottish-football display names are synthetic MVP
fixtures. Demo seeding and the administration surface are forbidden outside
local/test configuration.

## Trust boundaries

```text
Administrator browser -> React admin workspace -> FastAPI admin routes
                                             -> PostgreSQL metadata, versions
                                                and audit
Approved template reference -> operator-deployed compatible Camunda definition

Service-request content repositories and Camunda task mutation are not
administration dependencies.
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
| A hierarchy edit creates a cycle, orphan or skipped level | Validate the complete immutable candidate version, route closure and unit kinds before it can await approval |
| Candidate-group injection redirects work | Select only governed mappings that resolve to compatible operator-deployed groups; never accept an executable expression or browser-supplied group at activation |
| Configuration removes every complete route | Require at least one valid Customer-to-team path; surface an unstaffed valid team as `Awaiting team staffing` without silent fallback |
| One administrator authors and activates a high-impact change | Require reason, deterministic preview, unexpired session-bound step-up and approval by a different authorised configuration approver |
| Approval applies to content changed afterwards | Approve the immutable version and digest only; any edit creates a new draft requiring validation and approval |
| Arbitrary BPMN or code enters through administration | Accept only an allow-listed declarative template schema referencing a compatible BPMN version deployed through the operator path |
| Activation changes an in-flight request | Pin organisation, form, workflow and notification-policy versions at submission and forbid implicit instance migration |
| Concurrent activations create two active versions | Lock the activation boundary, require the expected version and make one transaction the winner |
| Rollback erases attribution | Activate a validated superseding version and retain every prior version, approval and request pin |
| Domain allow-list grants request-content access | Keep link-domain policy as metadata; administration never resolves released products or Customer recipients |
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
- Cycle, orphan, skipped-level, duplicate, candidate-group and no-complete-route
  configuration validation tests.
- Same-actor approval, expired step-up, changed-after-review, unauthorised
  approver and concurrent-activation tests.
- Declarative-schema abuse and incompatible BPMN tests proving that scripts,
  expressions, arbitrary BPMN and weakened mandatory fields cannot be activated.
- Historical rename, move, retirement, as-of query, superseding rollback and
  in-flight version-pinning tests.
- Explicit Administrator denial for release content and recipient data while
  managing approved product domains.
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
- Configuration activation remains blocked until approver membership, emergency
  superseding authority and candidate-group ownership have named operational
  owners.
