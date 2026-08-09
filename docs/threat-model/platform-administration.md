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
| A crafted request bypasses the filtered parent selector | Treat compatible-parent filtering as guidance only; validate the complete proposed hierarchy, effective windows and immediate parent kind on the server |
| Search or breadcrumbs disclose unrelated application content | Build them only from the administrator-authorised configuration response; keep request, product, Customer and task repositories outside the administration path |
| Search permits enumeration or denial of service | Enforce the bounded configuration size at the API, use local literal case-insensitive matching without regular expressions, and avoid logging search text |
| HTML or Unicode content makes a unit appear to be another unit | Render labels through React escaping, retain the stable code beside the display name, constrain and normalise input, and require sibling uniqueness; confusable-name policy remains an enterprise decision |
| A stale search result or parent option is applied after another change | Require `expectedVersion`, lock the proposed configuration and revalidate the complete snapshot; return a conflict without partial mutation |
| A scheduled move or retirement is hidden from the approver | Compare every future effective checkpoint, show each distinct transition time and bind approval and activation to the canonical snapshot digest |
| A false preview hides or invents workflow impact | Canonicalise unordered template values and distinguish existing validation findings from newly introduced change impact; approval binds to the immutable exact snapshot |
| A move silently broadens management or tracking scope | Preview permission impact, rebuild organisation closure atomically on activation, and test removal of former-ancestor access as well as addition of the new path |
| Candidate-group injection redirects work | Select only governed mappings that resolve to compatible operator-deployed groups; never accept an executable expression or browser-supplied group at activation |
| Configuration removes every complete route | Require at least one valid Customer-to-team path; surface an unstaffed valid team as `Awaiting team staffing` without silent fallback |
| One administrator authors and activates a high-impact change | Require reason, deterministic preview, unexpired session-bound step-up and approval by a different authorised configuration approver |
| Approval applies to content changed afterwards | Approve the immutable revision and canonical digest only; reject digest mismatch at activation; PostgreSQL guards deny component changes once the proposal leaves Draft |
| A direct database insert fabricates approval or activation evidence | PostgreSQL insert guards require the exact lifecycle revision, approved digest linkage, active Platform Administrator actors, creator separation, activation lineage and valid event order; runtime readiness independently rechecks the same structure |
| An approved workflow record changes after the snapshot is reviewed | PostgreSQL seals process ID, process revision, compatibility key, checksum, approver and approval time; the snapshot digest binds its immutable identifier while availability and deployment key remain controlled operational state |
| Arbitrary BPMN or code enters through administration | Accept only an allow-listed declarative template schema referencing a compatible BPMN version deployed through the operator path |
| Activation changes an in-flight request | Pin organisation, form, workflow and notification-policy versions at submission and forbid implicit instance migration |
| Concurrent activations create two active versions | Lock the activation boundary, require the expected version and make one transaction the winner |
| Rollback erases attribution | Activate a validated superseding version and retain every prior version, approval and request pin |
| Domain allow-list grants request-content access | Keep link-domain policy as metadata; administration never resolves released products or Customer recipients |
| Staffing display drifts from access reality | Recalculate from active, role-qualified Manager and Analyst memberships after relevant mutations; preserve the derived result on reseed |
| An administrator-created Team Manager lacks operational authority | Create audited exact-team management grants in the account transaction and revoke those standard grants when role, team or status changes |
| A restart overwrites activated organisation configuration with fixtures | Restore and rematerialise the immutable active version at startup; seed the synthetic baseline only when no active configuration exists |
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
- Direct runtime-role evidence-insert denial for invalid actors, revision,
  digest, lineage and event order, plus readiness rejection of forged structure.
- Scheduled-transition preview, canonical-digest mismatch and PostgreSQL sealed
  snapshot mutation tests.
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
- Literal name, code and kind search; ancestor-context breadcrumb; no-result;
  narrow-width; and filtered-parent component and browser tests.
- Forged parent, stale result, scheduled retirement, closure rebuild and former
  ancestor denial tests proving that the UI filters are not security controls.
- Canonical unchanged-comparison tests proving that value ordering and an
  existing staffing warning do not invent a change.

## Residual risks and exit gates

- One shared weak password prevents individual credential assurance. It is
  accepted only for an isolated synthetic local/test MVP.
- Sequential usernames are intentionally discoverable and require no secrecy.
- Account-only lockout can be abused to deny a predictable user access. Before a
  connected pilot, add an approved trusted-edge source limiter or shared throttle
  with safe proxy handling, alerting and a documented unlock procedure.
- PostgreSQL now independently seals non-Draft configuration components, but the
  administrative audit table still lacks an independent append-only storage
  boundary and structured correlation/outcome fields.
- The shared application database identity cannot itself prove which human
  initiated a structurally valid privileged write. A connected production
  design requires separately controlled evidence writing or identity-bound
  signatures, with the audit copy exported to an independent security boundary.
- Before any pilot or production use, replace demo authentication with approved
  identity, privileged-access, joiner/mover/leaver and recovery processes.
- Production requires restricted database grants, audit monitoring, backup and
  restore evidence, dependency and secret scanning, and authorised staging DAST.
- Configuration activation remains blocked until approver membership, emergency
  superseding authority and candidate-group ownership have named operational
  owners.
