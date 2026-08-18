# Audit event catalogue

Status: implemented events and enterprise-required events distinguished
Last reviewed: 18 August 2026

## Common envelope

Administrative audit records currently contain an event identifier, actor,
target type and stable identifier, timestamp, safe changed-field-name list,
content-free summary, previous hash and event hash. They
must not contain request narrative, clarification text, product content,
credentials, cookies, CSRF values, connection strings or raw Camunda variables.

Correlation identifiers, structured outcomes and event-specific before/after
values are not yet part of the administrative audit schema. The table below
therefore distinguishes a recorded lifecycle action from its complete
enterprise metadata requirement. Configuration approval and activation bind a
canonical snapshot digest in their own immutable evidence records; the digest is
not currently duplicated into the administrative hash chain.

A separate content-free security-event stream records bounded event type,
outcome, reason code, actor identifier where known, keyed subject/source hashes,
correlation identifier and matched request method/route where applicable. It is
append-only in application behaviour and commits independently when a denied
request cannot share the caller's failed transaction. It never stores passwords,
bearer or CSRF credentials, submitted content or raw source identifiers.

Configuration lifecycle events retain their internal identifiers for stable
machine consumers even though the interface says proposed changes.

| Internal event | Operator meaning | Required metadata | State |
|---|---|---|---|
| `CONFIGURATION_DRAFT_CREATED` | Proposed changes created | Base identifier, title, effective time, actor | Partial: action and safe changed-field names recorded |
| `CONFIGURATION_DRAFT_REPLACED` | Proposed changes updated | Expected/new revision, changed safe fields, actor | Partial: action and safe changed-field names recorded |
| `CONFIGURATION_VALIDATED` | Complete validation performed | Revision, result and finding codes, not request content | Partial: action recorded; structured result/codes required |
| `CONFIGURATION_SUBMITTED` | Submitted for independent review | Exact revision, reason and actor | Partial: action recorded; structured revision/reason required |
| `CONFIGURATION_APPROVED` | Proposed changes approved | Reviewed revision, snapshot digest, different actor and reason | Partial: action recorded; digest exists in approval evidence |
| `CONFIGURATION_REJECTED` | Proposed changes rejected | Reviewed revision, snapshot digest, actor and reason | Partial: action recorded; digest exists in approval evidence |
| `CONFIGURATION_ACTIVATED` | Approved changes made current | Digest, effective time, previous/current IDs, actor and reason | Partial: action recorded; digest exists in activation evidence |
| `CONFIGURATION_SUPERSEDED` | Previous configuration retained | Previous/current IDs and activation correlation | Partial: action recorded; structured correlation required |
| Account create/update/status | Identity metadata changed | Stable user ID, safe prior/next fields and actor | Partial: action and safe changed-field names recorded; exact structured before/after required |
| Membership/grant change | Team authority changed | Stable user/team/grant IDs, effective window and actor | Partial: action recorded; exact structured grant/effective-window before/after required |
| Human routing outcome | Named user selected or returned a route | Request/work identifiers, source/destination stable IDs, outcome | Implemented workflow audit |
| Parent rejected | Forged or stale hierarchy change denied | Actor, proposed child/parent stable IDs, reason code | Required before production SIEM |
| Concurrent edit rejected | Stale administrative write denied | Target, supplied/current revision and correlation | Required before production SIEM |
| Step-up success/failure/expiry | Privileged confirmation state changed | Actor, session-safe identifier, outcome, no password | Implemented in the content-free security-event stream; production SIEM export and retention remain required |
| Search abuse limited | Excessive configuration enumeration blocked | Actor, count/window and outcome, not query text | Required if server-side search is introduced |
| Recovery applied | Superseding or reconciliation action performed | Authority, target, reason and before/after integrity result | Partial: workflow recovery appends a content-free request event; independent operator outcome and production authority remain required |

## Implemented security outcomes

| Event | Recorded boundary | Content-minimised result |
| --- | --- | --- |
| `LOGIN` and `LOGIN_RATE_LIMIT` | Authentication success, neutral credential failure and admission-budget denial | Outcome and reason with keyed subject/source hashes; no submitted password or raw identifier |
| `STEP_UP` | Privileged confirmation success, failure and expiry | Actor, outcome and reason only; rotated bearer and CSRF values are never recorded |
| `CSRF_DENIAL` and `ROLE_DENIAL` | Mutation boundary rejects CSRF/origin proof or required Platform Administrator role | Actor, bounded outcome and reason |
| `AUTHORIZATION_DENIAL` | Authenticated mutation fails object or action policy | Actor, correlation identifier, method and route template without target content |
| `IDENTITY_CONTEXT_SWITCH` | Effective Customer/Staff context changes or is denied | Actor plus keyed prior/next context subject; replacement credentials are excluded |

## Access and retention

- Platform Administrators may view safe administrative history but gain no
  request-content access.
- Security and Support Operators require separately approved read-only access in
  production. No such implicit application role exists in the MVP.
- Runtime database roles must not update or delete audit events. Independent
  append-only enforcement remains an enterprise exit gate.
- Retention, export, legal hold and SIEM ownership require named decisions before
  production. Historical local evidence does not set production retention.

## Integrity verification

Verification recomputes each canonical event hash from the trusted anchor and
checks the prior-hash chain in order. A mismatch fails operational assurance and
is escalated as a potential security incident. Recovery never rewrites the
broken chain.
