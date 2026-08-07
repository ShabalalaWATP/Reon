# Service Request Workflow Threat Model

## Scope and assets

Assets include synthetic user accounts, server-side sessions, submitted request
content, workflow identifiers, organisation routes, assignments, action and
notification projections, versioned product packages, managed artefacts, approved
external links, dissemination and access records, feedback and append-only audit
history. Camunda, PostgreSQL, private object storage and the scanner are trusted
service boundaries, not browser-facing authorities.

The Platform Administrator is a supporting principal with access to identity,
role, team and safe configuration metadata only. Administrative status does not
grant request-content access.

## Trust boundaries

```text
Browser -> React -> FastAPI -> Product PostgreSQL
                         -> Camunda V2 API -> Camunda-owned storage
Browser -> single-purpose upload intent -> private quarantine object store
Quarantine object store -> format and malware scanner -> released object store
Browser -> authorised short-lived grant -> private released object store
Authenticated redirect -> approved external HTTPS destination (browser only)
```

## Principal threats and controls

| Threat | Control |
| --- | --- |
| Another Customer reads a request | Query by Customer ID and recheck object ownership on detail and product access |
| A staff member performs another role's action | Server-side role-to-stage policy and expected-status check before every mutation |
| A user manipulates an object identifier | Recheck role, scope, ownership or assignment on the loaded object and return a non-disclosing denial |
| Related-work search leaks records | Require the active claimed JIOC task and route membership in the candidate query; return bounded metadata only |
| A link target changes between search and save | Revalidate target scope and released-product state in the locked source transaction |
| Duplicate or concurrent link submissions | Source optimistic version, row locks and unique source/target/type constraint produce one winner |
| A possible duplicate is treated as workflow truth | Keep links informational and append-only; never change Camunda variables or request state from a link |
| An action projection becomes a second task authority | Keep source and source version on every projection; invoke only named use cases that recheck authoritative state and never mutate from the projection itself |
| A stale action is presented as current | Return measured freshness and source version, reject stale mutations with conflict metadata and repair projections idempotently |
| Notification retry creates duplicates | Use the source event plus recipient as a unique idempotency key and reconcile through the transactional outbox |
| A notification leaks protected content | Store a minimum safe subject only; exclude request narrative, clarification text, product content, Customer identity and private calendar text from payloads, logs and metrics |
| A copied notification deep link grants access | Recheck current recipient, role, object, assignment and organisation policy at the target endpoint; notification possession is never authority |
| Administrator uses support role as a content bypass | Separate metadata ports and routes; deny administrator request list, detail and mutation policy |
| A stolen Administrator session changes access | Require password step-up bound to that opaque session, CSRF and trusted origin; expire elevation after five minutes |
| Elevation is replayed in another browser session | Store elevation only on the server-side session row and return only its expiry time |
| Repeated step-up guesses bypass login controls | Use the same Argon2 verifier, generic failure and bounded account lock policy; invalidate locked-account sessions |
| An Analyst self-approves or disseminates work | Separate Manager and QC roles, immutable author ID and final-boundary checks |
| A routing user submits a fabricated, skipped or unrelated unit ID | Load valid direct children server-side and recheck stage, parent, actor role, request version and selected path before deriving the Camunda candidate group |
| A browser supplies a candidate-group name | Ignore browser group values; derive candidate groups from governed organisation records in FastAPI |
| An alternative team silently receives OSG staff | Scope Team Manager and Analyst tasks to the selected team; represent missing membership as `Awaiting team staffing` |
| Administrative account changes remove the last Manager or Analyst | Recalculate staffing from active role-qualified memberships after every relevant change; keep the team selectable and surface `Awaiting team staffing` rather than falling back |
| Tracking access becomes content or cross-unit access | Use a dedicated metadata-only projection and response schema; SQL-scope rows by the actor's selected JIOC, command or Ops membership before they leave persistence; never reuse request detail or product repositories |
| Cross-site request forgery | HttpOnly SameSite session cookie plus per-session CSRF header token and trusted-origin checks |
| High-frequency reads contend on session activity writes | Validate expiry, idle state, account state and credential version on every request, but persist `last_seen_at` only after half of the configured idle window has elapsed |
| Session theft or replay | Random opaque token, hash at rest, expiry, rotation on login and invalidation on logout |
| Password guessing | Argon2id, bounded failures, temporary lockout and generic authentication errors |
| Stored script injection | Pydantic length constraints, React escaping and plain-text product rendering |
| SQL injection | SQLAlchemy bound parameters and constrained sort/filter fields |
| Duplicate process starts | Transactional outbox, request UUID business ID, Camunda business-ID uniqueness and idempotent dispatch |
| An expired dispatcher lease lets a stale worker overwrite success | Random lease generation token and conditional state update; stale success or retry results are ignored |
| A stale or repeated task action changes state | Commit a durable intent first, then recheck the active actor, scope, assignment, task, state and version immediately before dispatch |
| API stops after the engine effect | Recover only from the exact Camunda task, expected next task or explicit terminal process state |
| Workflow and projection drift | Recoverable command leases, expected task-element checks, bounded retry, and version/process-key-fenced reconciliation with a visible support-owned error state |
| A terminated process is treated as a successful dissemination | Only `COMPLETED` proves a terminal human action; `TERMINATED` follows a separate support path and cannot release a product |
| Audit history is altered | Canonical event hashes, prior-hash chaining and tested integrity verification; database-level append-only grants remain a production gate |
| Direct Camunda access | Bind local ports to loopback; production uses private networking, OIDC and explicit client authorisation |
| Sensitive data in logs | Structured event metadata only; never log passwords, cookies, CSRF tokens or request bodies |
| Backup is missing, unreadable or incomplete | Encrypted scheduled backup, restricted restore access and evidenced restore rehearsal before pilot |
| A forged upload intent writes an arbitrary object | Issue a short-lived single-purpose intent with a server-chosen key, size and media type; quarantine identity cannot write released storage |
| A malicious or disguised file reaches review | Check extension, media type, magic bytes, Office structure, encryption, archive expansion and active content, then require a current clean malware result before promotion |
| Scanner failure or stale result is treated as success | Fail closed for unknown, failed, timed-out or superseded scans; bind promotion to object checksum and scan-policy version |
| Quarantined or released objects become public | Deny public bucket access, separate storage privileges and test unauthenticated object retrieval before release |
| An artefact changes after approval | Bind Manager review and QC dissemination to the immutable package version and checksum; any change creates a new version and invalidates approval |
| A guessed or shared product object is retrieved | Authorise the active Customer, dissemination and artefact lifecycle on every download before issuing a short-lived grant or stream |
| An external product link enables SSRF | Accept constrained absolute HTTPS links but never fetch or preview them in the backend |
| Link normalisation bypasses the allow-list | Normalise once and reject credentials, fragments, non-standard schemes, loopback, literal private-network hosts and domains outside the versioned allow-list |
| An expired or withdrawn external product opens | Recheck recipient, release, expiry and lifecycle in the authenticated redirect and apply safe browser isolation |
| Synthetic identity confusion | Display one environment-level mock-data notice and document that identities and public-safe sibling names are fictional; do not mark valid routes as demonstration-only |
| Product link is guessed or shared | Serve through an authenticated, no-store application endpoint; require the originating Customer, completed state and dissemination record on every request |
| Product response causes active-content execution | Return UTF-8 plain text with safe reference-derived attachment filename, `nosniff` and restrictive security headers |
| Analyst clarification exposes product work to trackers | Store a structured thread in PostgreSQL; expose messages only to the Customer, assigned Analyst and authorised Team Manager; project state and timing metadata only to routing trackers |
| Clarification response loses the delivery assignment | Persist the team and Analyst on the thread, validate them on response and route the versioned workflow loop back to that Analyst |
| Two open clarification requests race | Lock the request, require expected state and version, and enforce one open thread per request while permitting sequential closed threads |
| A retry creates duplicate Customer or Analyst tasks | Use stable clarification command keys and outbox uniqueness; prove repeated dispatch and reconciliation are idempotent |
| An older process instance receives the new loop | Deploy a new BPMN version, record process-definition version per request and leave existing instances pinned |

## Residual risks and go-live gates

- Local Docker Compose and no-auth Camunda are development-only.
- Production identity and per-user Camunda audit require shared OIDC or an approved
  token-exchange design.
- Camunda Self-Managed production licensing must be confirmed before go-live.
- The MVP account lockout is not a durable, multi-replica source-rate limiter.
  Production requires an approved edge limiter or a dedicated shared throttle
  store, with safe proxy-address handling and operational monitoring.
- A production candidate needs dependency, secret, container and DAST scans plus
  an authorised staging test. Local MVP evidence does not authorise production.
- Application runtime bases are digest-pinned and must pass the high and critical
  image gate against a current vulnerability database. A clean historic report
  does not override a later database result; a failing base is replaced or an
  explicit, time-bounded risk decision is required before release.
- The local schema is migrated by the product runtime database owner. Before a
  pilot, use a distinct migration owner, deny runtime UPDATE and DELETE on audit
  tables, grant only required sequence/table operations, and schedule an integrity
  verification job with an owned alert path.
- Managed artefacts cannot be enabled until file and package limits, production
  storage region, encryption-key ownership, scanner operation, quarantine
  response and retention have named owners and tested runbooks.
- Approved external destinations remain third-party trust boundaries. QC must
  attest Customer access and handling suitability; ISTARI Service cannot prove
  the destination's continued availability or content after redirect.

## Required abuse-case evidence

- Cross-role and cross-scope list, detail, search and mutation tests.
- Direct-identifier tests for requests, tasks, outputs, feedback and admin objects.
- Invalid, skipped, duplicate and stale workflow-transition tests.
- Complete alternative-branch candidate-group tests with distinct Manager and
  Analyst identities, plus dynamic unstaffed-team tests with no OSG fallback.
- Metadata-only tracker tests and pre-dissemination, cross-Customer and malformed
  product-download denials.
- Expired, replayed, disabled-account, login-throttling, origin and CSRF tests.
- Administrator denial tests for every request-content endpoint.
- Audit-chain verification and safe-logging assertions.
- Engine outage, database rollback, outbox retry and duplicate-command tests.
- Analyst clarification scope, repeated-loop, same-assignment, competing-open and
  process-version tests.
- Action-source, stale-state, pagination and cross-scope deep-link tests proving
  that action projections cannot change workflow state directly.
- Notification event-recipient, replay, content-minimisation, revoked-access,
  disabled-account, lag and reconciliation tests.
- PDF, DOCX and PPTX validation and malware corpus tests, including mismatched,
  macro-enabled, encrypted, expanded, oversized, timed-out and orphan cases.
- Upload-intent forgery, public-object probe, immutable package version,
  pre-release, cross-Customer, replaced and withdrawn download tests.
- External-link scheme, credential, fragment, private-host, allow-list, expiry,
  no-fetch and authenticated-redirect tests.
- Object-store and scanner interruption, quarantine, cleanup and joined restore
  rehearsals.
- Backup restore and recovery-point verification before pilot exit.
