# Service Request Workflow Threat Model

## Customer intake and account-request boundary

The Customer request contract excludes service classification, internal business areas, routing destinations and intended recipients. This reduces topology disclosure and prevents a requester from influencing classification, authorisation or routing through untrusted form values. The persisted service-category value is server-owned compatibility metadata and is not part of Customer input. The authenticated requester identity is bound server-side and is the eventual dissemination recipient.

Every workflow-submitted field is mandatory and bounded at both the React and FastAPI boundaries. Cross-field date rules execute server-side. Private drafts may be incomplete but receive the same length and type limits, and draft submission is revalidated as a complete request.

The session profile returns organisation-unit identifiers only for the signed-in
identity. A separate self-profile endpoint stores optional Team or business area,
Rank or grade, Service number and Additional information. Those values do not
grant access, are never used for routing and are returned only to the signed-in
identity. Every
request, work, statistics and organisation endpoint continues to reapply its
server-side object, role and membership policy. Customer action prompts are
shown on `My requests` and through minimal notifications; notification links do
not confer authority.

Unauthenticated account requests accept only a display name, normalised work email and access reason. They do not accept credentials, role, scope or memberships. Duplicate pending emails receive the same accepted response to limit account enumeration. The endpoint is restricted to environments where synthetic demo identities are enabled. Administrative approval requires an authenticated Platform Administrator, CSRF validation, recent password step-up and optimistic version matching. Approval can create only a Customer role through this path and is written to the administration audit chain.

## Password assistance and global marking

The public password-assistance endpoint can be used to probe identities or flood
administrators. Every valid-looking email receives the same HTTP 202 response,
regardless of account existence, activity, throttling or recent requests. The
submitted address is normalised for the lookup but is never persisted in the
attempt record or copied into logs. Attempts retain a one-way source key and an
optional internal account identifier, expire after seven days, and are bounded
by shared PostgreSQL source and global windows. A per-account cooldown suppresses
duplicate notifications. All active Platform Administrators receive the same
mandatory, content-minimised in-app event, so no single administrator becomes a
silent availability dependency. A managed edge control remains required against
distributed volumetric abuse.

A stolen or stale administrator session could otherwise downgrade the global
visual marking. Mutation therefore requires the Platform Administrator role,
trusted origin and CSRF checks, a fresh password step-up, row locking and the
expected singleton version. The audit chain records the actor and old/new
classification. The unauthenticated read returns only the marking, version and
timestamp. The interface and architecture explicitly state that the strip is a
visual marking only: it cannot grant access, reclassify request content or
replace request-level handling policy. Client caching may delay another open tab
by at most its short refresh interval, while focus refresh and mutation cache
updates normally converge sooner.

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
| A Customer cancels another or stale request | Lock the request, require exact Customer ownership, a non-terminal state and optimistic version, then return a non-disclosing denial or conflict |
| Cancellation closes PostgreSQL but leaves active work | Atomically cancel local tasks, packages and reservations and enqueue a fenced Camunda termination command; suppress a start that has not left PostgreSQL |
| An uncertain Camunda cancellation is replayed | Use one idempotent outbox key and prove the exact process is `TERMINATED` before recording command success |
| Cancellation notifications expose the reason or accept browser recipients | Keep the subject content-free, derive recipients from server-owned route selections and assignments, and retain the reason only in authorised request activity |
| Self-entered profile data changes access | Keep personal fields in a dedicated self-profile contract and never consume them in role, scope, membership, routing, statistics or workflow policy |
| A user reads or edits another profile | Bind the profile row to the authenticated actor server-side; accept no user ID and require CSRF plus optimistic concurrency for updates |
| Service number or profile narrative leaks through secondary systems | Exclude self-profile fields from sessions, notifications, analytics and logs; bound and render them as escaped plain text |
| A staff member performs another role's action | Server-side role-to-stage policy and expected-status check before every mutation |
| A user manipulates an object identifier | Apply both database-scoped lookup and a typed service decision for the named operation; recheck role, route, team, ownership or assignment and return the same `404` body for missing and inaccessible objects |
| Repeated request/work checks drift into inconsistent permissions | Keep request and active-work operations in one framework-independent typed policy, preserve separate bounded grant models for other object types, and enforce cross-role, sibling-route, assignment and direct-identifier matrices at the public API |
| Oversized or non-JSON audit evidence bypasses stable hashing or exhausts verification | Validate a bounded recursive JSON evidence type before append and again during typed chain verification; permit unknown safe keys but reject unsupported types, non-finite numbers, unsafe keys, excess depth and excess collection size |
| Related-request ranking leaks records or excerpts | Require the active claimed CRIOC task and apply route membership independently to lexical, vector, comparison and save queries before returning bounded metadata, scores or excerpts |
| Embedding generation exfiltrates submitted content | Bake the approved model into the backend image, load it offline only and prohibit runtime calls to external model providers |
| A poisoned or malformed request exhausts the indexer | Reuse bounded validated request fields, cap projection bytes and worker batch size, fence the named job and keep submission and text search independent of embedding success |
| A match score is treated as duplicate truth | Label it match strength, expose deterministic contributing fields, retain explicit human decisions and never change routing, priority or Camunda state from ranking |
| Semantic indexing fails or becomes stale | Store model and projection versions, expose text-only fallback, reconcile pending rows and require controlled re-indexing for model upgrades |
| A link target changes between search and save | Revalidate target scope and released-product state in the locked source transaction |
| Duplicate or concurrent link submissions | Source optimistic version, row locks and unique source/target/type constraint produce one winner |
| A possible duplicate is treated as workflow truth | Keep links informational and append-only; never change Camunda variables or request state from a link |
| An action projection becomes a second task authority | Keep source and source version on every projection; invoke only named use cases that recheck authoritative state and never mutate from the projection itself |
| A stale action is presented as current | Return measured freshness and source version, reject stale mutations with conflict metadata and repair projections idempotently |
| A staff action link opens a Customer-only page or an unrelated queue item | Generate role-aware relative queue links, filter the actor-scoped work query by request UUID and show an ended-action state when no authorised task remains; never fall back to the first queue item |
| A copied request UUID enumerates another unit's task | Treat `requestId` only as an additional selector inside the existing role, membership, task-state and assignee predicates; return the same empty result for missing and inaccessible work |
| Shared work remains visible after another user claims it | Reproject the action to the proven Camunda task assignee in the same request-event transaction and require current task ownership on every queue read and mutation |
| Notification retry creates duplicates | Use the source event plus recipient as a unique idempotency key and reconcile through the transactional outbox |
| A notification leaks protected content | Store a minimum safe subject only; exclude request narrative, clarification text, product content, Customer identity and private calendar text from payloads, logs and metrics |
| A copied notification deep link grants access | Recheck current recipient, role, object, assignment and organisation policy at the target endpoint; notification possession is never authority |
| Administrator uses support role as a content bypass | Separate metadata ports and routes; deny administrator request list, detail and mutation policy |
| A stolen Administrator session changes access | Require password step-up bound to that opaque session, CSRF and trusted origin; expire elevation after five minutes |
| Elevation is replayed in another browser session | Store elevation only on the server-side session row and return only its expiry time |
| Repeated step-up guesses bypass login controls | Use the same Argon2 verifier, generic failure and bounded account lock policy; invalidate locked-account sessions |
| An Analyst self-approves or disseminates work | Separate Manager and QC roles, immutable author ID and final-boundary checks |
| A routing user submits a fabricated, skipped or unrelated unit ID | Load valid direct children server-side and recheck stage, parent, actor role, request version and selected path before deriving the Camunda candidate group |
| A route breadcrumb or destination search leaks sibling or ancestor data | Build both only from the server-authorised selected request path and direct-child destination response; never join to global organisation or request-content data in the browser |
| Broad route search creates enumeration or denial of service | Return only direct children, cap local input at 120 characters, use literal case-insensitive matching and avoid logging search text |
| Configuration changes between destination display and submission | Pin each request, require expected request/task state and revalidate the selected effective child in the locked human-outcome use case |
| Staffing or workload indicators become automated routing | Present factual bounded state without ranking, recommendation, default selection or automatic fallback; the named user remains accountable |
| A browser supplies a candidate-group name | Ignore browser group values; derive candidate groups from governed organisation records in FastAPI |
| An alternative team silently receives SSG staff | Scope Team Manager and Analyst tasks to the selected team; represent missing membership as `Awaiting team staffing` |
| Administrative account changes remove the last Manager or Analyst | Recalculate staffing from active role-qualified memberships after every relevant change; keep the team selectable and surface `Awaiting team staffing` rather than falling back |
| Tracking access becomes cross-unit or operational access | Apply exact selected-route membership inside list, direct-detail and coordination queries; keep monitoring separate from actionable work; route membership alone never permits claim, completion or transfer; return a non-disclosing not-found response outside scope |
| Monitoring messages leak request content or become an ownership bypass | Re-authorise every read and write against the immutable selected route and current request state; address messages only to the Customer or current owner; exclude message text from notifications, logs and telemetry; append a hash-linked event without changing workflow state |
| A previous handler seizes work through a return request | Restrict targets to the user's unit or an earlier unit on the selected route; make the request append-only and non-mutating; require current owners to use existing authorised workflow return actions; record the request and subsequent stage transitions in the hash-linked event history |
| A statistics user selects a parent or sibling unit | Resolve the active grant server-side, require the selected unit to be its root or an authorised configured descendant through the organisation closure, and return a non-disclosing not-found response otherwise |
| A cached hierarchy leaks a previously authorised branch | Key protected queries by actor, grant and selected unit, reauthorise every API and export read, and remove disabled or revoked units from server responses immediately |
| Multiple grants become an implicit cross-branch scope | Treat every grant as an independent root and require an explicit scope switch; never build navigation edges between separately granted sibling roots |
| Drill-down defeats cohort suppression | Recalculate suppression independently for the selected node and retain content-free facts, so ancestor and descendant navigation cannot reveal protected individual or request content |
| Cross-site request forgery | HttpOnly SameSite session cookie plus per-session CSRF header token and trusted-origin checks |
| High-frequency reads contend on session activity writes | Validate expiry, idle state, account state and credential version on every request, but persist `last_seen_at` only after half of the configured idle window has elapsed |
| Session theft or replay | Random opaque token, hash at rest, expiry, rotation on login and invalidation on logout |
| Password guessing or unknown-account hash exhaustion | Durably consume shared PostgreSQL global and source budgets in a cancellation-shielded short transaction before account lookup or Argon2; bound acquisition, statement, row-lock and cancellation time; release the shared lock before bounded hash work; retain Argon2id, temporary account lockout and generic errors |
| Database contention turns cancellation shielding into task or pool exhaustion | Apply one end-to-end limiter deadline and shorter transaction-local PostgreSQL statement/lock deadlines; fail unavailable before account lookup or hashing and ensure the operation terminates after caller cancellation |
| A client evades source throttling with a forged forwarding header | Trust one forwarded address only from an explicitly configured proxy CIDR, canonicalise it and store only a one-way source digest |
| Stored script injection | Pydantic constraints, React escaping, strict managed-file validation, attachment-only authenticated downloads, safe external-link redirects and restrictive response headers |
| SQL injection | SQLAlchemy bound parameters and constrained sort/filter fields |
| Duplicate process starts | Transactional outbox, request UUID business ID, Camunda business-ID uniqueness and idempotent dispatch |
| An expired dispatcher lease lets a stale worker overwrite success | Random lease generation token and conditional state update; stale success or retry results are ignored |
| A stale or repeated task action changes state | Commit a durable intent first, then recheck the active actor, scope, assignment, task, state and version immediately before dispatch |
| API stops after the engine effect | Recover only from the exact Camunda task, expected next task or explicit terminal process state |
| Workflow and projection drift | Recoverable command leases, expected task-element checks, bounded retry, and version/process-key-fenced reconciliation with a visible support-owned error state |
| Recovery replays a permanent or malformed workflow failure | Requeue only exact retry-exhaustion markers for claim or completion and the exact transient start failure; preserve every other failure for support review |
| A workflow engine returns an unexpected process after start | Compare the returned process ID and version with the immutable pending-start identity before projecting success |
| The maintenance worker dies silently | Persist a content-free heartbeat from the separately supervised worker and fail API readiness after the configured stale threshold |
| A terminated process is treated as a successful dissemination | Only `COMPLETED` proves a terminal human action; `TERMINATED` follows a separate support path and cannot release a product |
| Audit history is altered | Canonical event hashes, prior-hash chaining and tested integrity verification; database-level append-only grants remain a production gate |
| Direct Camunda access | Bind local ports to loopback; production uses private networking, OIDC and explicit client authorisation |
| Sensitive data in logs | Structured event metadata only; never log passwords, cookies, CSRF tokens or request bodies |
| Backup is missing, unreadable or incomplete | Encrypted scheduled backup, restricted restore access and evidenced restore rehearsal before pilot |
| A forged upload intent writes an arbitrary object | Issue a short-lived single-purpose intent with a server-chosen key, size and media type; quarantine identity cannot write released storage |
| A malicious or disguised file reaches review | Check extension, media type, magic bytes, Office structure, encryption, archive expansion and active content, then require a current clean malware result before promotion |
| A local heuristic result is mistaken for production semantic assurance | Give every scanner runtime an explicit assurance class; advertise and permit managed-file uploads in production only for an injected `APPROVED_SEMANTIC_CDR` runtime. Local heuristic and ClamAV composition never self-identify as CDR |
| Scanner failure or stale result is treated as success | Fail closed for unknown, failed, timed-out or superseded scans; bind promotion to object checksum and scan-policy version; derive daily-definition age from signed build metadata and require equality between on-disk and loaded versions |
| A scanner protocol or archive parser is abused | Run strict PDF/Office structure checks before a bounded ClamAV `INSTREAM` scan; cap object bytes, archive entries, expanded bytes, compression ratio, scanner time and scanner response length |
| The malware service becomes a network pivot | Keep the untrusted-content clamd process non-root on a dedicated internal network, read-only signature mount and no published port or egress; give only a separate non-scanning updater outbound mirror access; use `INSTREAM` and never pass an application-controlled filesystem path |
| Quarantined or released objects become public | Deny public bucket access, separate storage privileges and test unauthenticated object retrieval before release |
| An artefact changes after approval | Bind Manager review and QC dissemination to the immutable package version and checksum; any change creates a new version and invalidates approval |
| A guessed or shared product object is retrieved | Authorise the active Customer, dissemination and artefact lifecycle on every download before issuing a short-lived grant or stream |
| Download or redirect probing is hidden | Append content-free allowed, denied and unavailable access evidence; deny runtime update and delete rights on the access-event table |
| An external product link enables SSRF | Accept constrained absolute HTTPS links but never fetch or preview them in the backend |
| Link normalisation bypasses the allow-list | Normalise once and reject credentials, fragments, non-standard schemes, loopback, literal private-network hosts and domains outside the versioned allow-list |
| An expired or withdrawn external product opens | Recheck recipient, release, expiry and lifecycle in the authenticated redirect and apply safe browser isolation |
| A withdrawn managed package falls back to an older product endpoint | Treat the existence of any managed package as authoritative and forbid legacy availability or download fallback |
| Synthetic identity confusion | Display one environment-level mock-data notice and document that identities and public-safe sibling names are fictional; do not mark valid routes as demonstration-only |
| Product link is guessed or shared | Serve through an authenticated, no-store application endpoint; require the originating Customer, completed state and dissemination record on every request |
| Product response causes active-content execution | Return UTF-8 plain text with safe reference-derived attachment filename, `nosniff` and restrictive security headers |
| Analyst clarification exposes product work to trackers | Store a structured thread in PostgreSQL; expose messages only to the Customer, assigned Analyst and authorised Team Manager; project state and timing metadata only to routing trackers |
| Clarification response loses the delivery assignment | Persist the team and Analyst on the thread, validate them on response and route the versioned workflow loop back to that Analyst |
| Two open clarification requests race | Lock the request, require expected state and version, and enforce one open thread per request while permitting sequential closed threads |
| A retry creates duplicate Customer or Analyst tasks | Use stable clarification command keys and outbox uniqueness; prove repeated dispatch and reconciliation are idempotent |
| A slow or failed Camunda call holds database locks and exhausts the pool | Commit a fenced outbox lease before Camunda I/O, then reauthorise and compare owner/generation in a new finalisation transaction |
| A timed-out workflow worker projects a stale result after lease takeover | Increment lease generation on every claim and reject finalisation unless owner and generation still match |
| A slow product upload, scan or download holds a metadata transaction | Split metadata validation, external I/O and fenced finalisation; close authorisation sessions before response streaming |
| A malformed or replayed page cursor widens visibility | Treat cursors only as bounded ordering keys and reapply full requester, role, route and team policy to every page |
| An older process instance receives the new loop | Deploy a new BPMN version, record process-definition version per request and leave existing instances pinned |

## Unified workspace and collaboration threats

| Threat | Control |
| --- | --- |
| A member forges another person's self-service calendar event | Self-event commands derive the subject from the authenticated session and reject subject, request and package identifiers. |
| Private leave or appointment notes leak into a shared calendar | Repository views redact by visibility before returning data; the client never receives concealed fields. |
| A routing Manager assigns or approves work outside the human-led route | Routing workspace capabilities exclude ticket assignment; the user must claim the Camunda task before recording a routing decision. |
| A Delivery Manager assigns an outsider or expired member | Assignment locks the request and resolves every participant against current exact-team membership at the command time. |
| An Analyst claims an unassigned production task instead of receiving a Manager assignment | Restrict claim commands to the explicit shared-decision role allowlist, exclude open Analyst tasks from projections and require Camunda production tasks to name the Manager-selected Lead Analyst. |
| Several assigned Analysts produce conflicting workflow outcomes | All active assigned Analysts share production authority, but one locked request version and one shared Camunda task produce a single winner; stale or later outcomes fail closed. |
| Concurrent handovers leave PostgreSQL and Camunda with different Leads | Optimistic request and participation versions select one winner; durable fenced commands reconcile Camunda and retain prior state. |
| Removing membership leaves request or cache access behind | Active leadership, participation and reservations require handover; membership and assignment mutations invalidate user-scoped protected caches. |
| A local Manager promotes a peer or crosses a unit boundary | Local administration accepts only compatible Member accounts in the exact unit; Manager appointment and global identity changes remain Platform Administrator actions. |
| Small-team statistics expose individual performance | Workspace statistics are aggregate, feedback is suppressed below its cohort threshold, and individual ranking is not implemented. |

## Residual risks and go-live gates

- Local Docker Compose and no-auth Camunda are development-only.
- Production identity and per-user Camunda audit require shared OIDC or an approved
  token-exchange design.
- Camunda Self-Managed production licensing must be confirmed before go-live.
- The application now has a durable PostgreSQL-backed global and source login
  limiter with explicit proxy trust and bounded Argon2 concurrency. Production
  still requires an approved edge WAF or limiter for broad volumetric defence,
  plus monitoring and capacity values validated against the deployed replica and
  ingress topology.
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
- The bundled private filesystem adapter and split ClamAV containers are local-pilot
  foundations. Local health now proves current loaded signatures. Production
  enabling still requires an explicitly injected private object-storage runtime,
  approved encryption and retention controls, and an internally reachable,
  monitored scanner service with an owned update and incident path.
- The local deterministic inspector rejects encoded PDF action names, object
  streams, incremental updates, embedded/active parts, OOXML external
  relationships, DDE, OLE and bounded archive abuse. It is not a semantic
  content-disarm-and-reconstruction service. Production managed documents remain
  blocked until an approved maintained parser or CDR boundary and adversarial
  corpus prove equivalent or stronger fail-closed behaviour.
- Product links and managed-file uploads have separate server capabilities.
  Production may keep allow-listed, non-fetched external links enabled while
  managed-file upload routes fail closed when semantic/CDR assurance is absent.
- Approved external destinations remain third-party trust boundaries. QC must
  attest Customer access and handling suitability; ISTARI Service cannot prove
  the destination's continued availability or content after redirect.
- Clean-object promotion and its database scan record are not yet one durable
  atomic operation. Before production object storage is enabled, introduce a
  persisted promotion state or transactional outbox plus orphan reconciliation,
  and prove crash recovery between object promotion and database commit.

## Required abuse-case evidence

- Cross-role and cross-scope list, detail, search and mutation tests.
- Direct-identifier tests for requests, tasks, outputs, feedback and admin objects.
- Invalid, skipped, duplicate and stale workflow-transition tests.
- Complete alternative-branch candidate-group tests with distinct Manager and
  Analyst identities, plus dynamic unstaffed-team tests with no SSG fallback.
- Direct-child search and route-breadcrumb tests, plus stale-destination,
  competing-claim and crafted-parent tests, including confirmation that no
  ranking or fallback occurs.
- Exact-route tracker list and direct-detail tests, including title and lifecycle
  visibility, sibling-route denial, and exclusion of actions, clarifications,
  feedback and product content; plus pre-dissemination, cross-Customer and
  malformed product-download denials.
- Expired, replayed, disabled-account, login-throttling, origin and CSRF tests.
- Administrator denial tests for every request-content endpoint.
- Audit-chain verification and safe-logging assertions.
- Engine outage, database rollback, outbox retry and duplicate-command tests.
- Analyst clarification scope, repeated-loop, same-assignment, competing-open and
  process-version tests.
- Lead and additional Analyst parity tests proving active roster membership at
  list, detail, intent, dispatch, product and clarification boundaries, plus
  immediate denial after assignment or team membership ends.
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
