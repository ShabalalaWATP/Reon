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
| Internal coordination appears in Customer history | Persist a server-owned event audience, backfill legacy `CURRENT_OWNER` and internal event types to `STAFF_ONLY`, and filter before pagination at every Customer history query |
| A removed or deactivated Lead or Contributor retains action or notification authority | Treat the Lead field and non-ended participant rows as accountability evidence only; at projection, every read, command dispatch and finalisation, revalidate an effective participant assignment, active Delivery Specialist account and live membership in the request's exact assigned team |
| A removed routing user or Team Lead retains a projected card or notification | For direct and candidate projections, revalidate live membership in the request's exact selected route unit; Team Lead access must also match the current assigned delivery team |
| A saved staff action view appears after switching to Customer context | Namespace saved views by stable identity and effective context, backfill existing rows as staff views and apply the context predicate to list, create, update and delete operations |
| A Customer enumerates staffing or organisation topology | Deny the global organisation reference endpoint to Customers; initialise submission routing from server-owned configuration only |
| A workspace link targets a local service or exploits URL parser differences | Canonicalise HTTPS links before persistence and reject credentials, fragments, controls, backslashes, unapproved ports and non-global destinations |
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
| A compatibility coordination retry duplicates immutable messages or exhausts quotas | Require a caller-stable client mutation UUID and pass it through the same sender-scoped idempotency check, request lock and admission controls as native conversations |
| Compatibility coordination copies target-only text into broadly visible history | Keep the body only in the target-authorised conversation; expose a generic legacy event with the existing body hash and immutable message reference as audit evidence |
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
| Hostile Office central-directory metadata exhausts parser memory | Parse only the bounded end-of-central-directory window first; reject Zip64, multi-disk, excessive entries and central-directory bytes before `ZipFile` construction, then cap concurrent document inspections |
| Parallel upload intents exhaust package or service storage before review | Reserve declared bytes while holding the singleton service quota plus owner, request and package locks; enforce package, request, author and service totals before issuing and again before persisting a grant |
| Upload finalisation fails after an object write or promotion | Compensate quarantine and released objects immediately, then run a fenced bounded reconciler for expired intents and unreferenced quarantine objects; deletion and expiry transitions are idempotent |
| Local product paths are replaced by symbolic links | Reject symbolic links in every object path component, use no-follow file descriptors where supported and retain root-contained atomic replacement semantics |
| The malware service becomes a network pivot | Keep the untrusted-content clamd process non-root on a dedicated internal network, read-only signature mount and no published port or egress; give only a separate non-scanning updater outbound mirror access; use `INSTREAM` and never pass an application-controlled filesystem path |
| Quarantined or released objects become public | Deny public bucket access, separate storage privileges and test unauthenticated object retrieval before release |
| An artefact changes after approval | Bind Manager review and QC dissemination to the immutable package version and checksum; any change creates a new version and invalidates approval |
| A covering note or artefact order changes after review | Bind the covering note, ordered manifest, artefact checksums and link records into one immutable package version; any change creates a new version and invalidates Manager and QC decisions |
| A hostile image exhausts a decoder or reaches the Customer as active content | Accept only bounded PNG and JPEG, check signature, dimensions, pixels, frames, metadata and complete decoding before malware scanning; reject SVG, animation, polyglots and decoder failure |
| An unreleased package reveals filenames, images, links, covering notes or review state | Keep package metadata staff-only until dissemination and apply object-level policy to existence, detail, download and redirect endpoints |
| One QC Manager approves and releases the same package | Store reviewer and releaser separately and revalidate distinct active identities, exact QC Team membership, immutable package version and recipient at release |
| A one-person QC Team silently bypasses separation | Block release, expose an `Awaiting independent releaser` state and alert the owned staffing path without borrowing authority from another unit |
| The QC Team becomes a request-routing shortcut or invalid hierarchy edge | Keep its stable membership identity outside the configured four-level routing tree; exclude it from route destinations and operational branch aggregation |
| Allowing QC identity administration admits arbitrary retired support units | Permit only the deterministic QC unit ID, code and Team kind for the Quality and Release role; retain configured-unit checks for every other role and do not create standard routing-management grants for QC membership |
| A guessed or shared product object is retrieved | Authorise the active Customer, dissemination and artefact lifecycle on every download before issuing a short-lived grant or stream |
| Download or redirect probing is hidden | Append content-free allowed, denied and unavailable access evidence; deny runtime update and delete rights on the access-event table |
| An external product link enables SSRF | Accept constrained absolute HTTPS links but never fetch or preview them in the backend |
| Link normalisation bypasses the allow-list | Normalise once and reject credentials, fragments, non-standard schemes, loopback, literal private-network hosts and domains outside the versioned allow-list |
| An expired or withdrawn external product opens | Recheck recipient, release, expiry and lifecycle in the authenticated redirect and apply safe browser isolation |
| A withdrawn managed package falls back to an older product endpoint | Treat the existence of any managed package as authoritative and forbid legacy availability or download fallback |
| A new package policy changes an in-flight or legacy product | Pin product mode, artefact policy and workflow version at package creation; require a separate audited migration to move existing records |
| Synthetic identity confusion | Display one environment-level mock-data notice and document that identities and public-safe sibling names are fictional; do not mark valid routes as demonstration-only |
| Product link is guessed or shared | Serve through an authenticated, no-store application endpoint; require the originating Customer, completed state and dissemination record on every request |
| Product acceptance is forged, replayed or inferred from access | Permit only the active originating Customer to accept the current non-withdrawn dissemination; require a unique idempotency key, append one hash-linked ticket event and never infer acceptance from download, redirect or feedback evidence |
| Customer and staff permissions combine into ambient authority | Bind one server-validated context to the session, namespace navigation and protected caches, and require an explicit CSRF-protected context transition |
| A deep link silently changes context | Authorise it in the active context or require an explicit context change; never accept context from an arbitrary request header |
| A dual-eligible user routes, assigns, reviews or releases their own request | Bind requester identity permanently and deny every staff action on that request for the same stable identity, regardless of context or later role changes |
| A dual-eligible user mutates a linked planning record for their own request | Recheck stable requester identity on package create, update, move and reservation changes, calendar commitments and task hasteners; exclude the requester as actor, owner, Contributor and reservation or commitment subject; return non-disclosing not-found responses |
| An expired QC role holder retains a notification deep link or direct request access | Require an active account, Quality and Release role and live Manager membership in the exact QC Team both before recipient projection and on notification, action, work and request-detail reads; bind effective-time comparisons at application precision |
| Context switching leaves protected data in the browser | Clear context-bound server state and client caches, refresh counts and reauthorise the destination before rendering |
| Product response causes active-content execution | Return UTF-8 plain text with safe reference-derived attachment filename, `nosniff` and restrictive security headers |
| Analyst clarification exposes product work to trackers | Store a structured thread in PostgreSQL; expose messages only to the Customer, assigned Analyst and authorised Team Manager; project state and timing metadata only to routing trackers |
| A conversation audience is omitted or a new entry type becomes public by default | Persist the narrowest staff-only audience, require an explicit supported audience and filter by current authority before ordering, pagination or cursor construction |
| A Customer-visible conversation leaks an internal note, assignment reason or recipient identifier | Keep typed entries and lifecycle summaries separate; expose only explicitly addressed Customer content and content-minimised public lifecycle records |
| Revoked membership remains visible through an old conversation cursor | Reapply account, context, route, ownership, team and assignment policy to every page and treat the cursor only as a bounded ordering key |
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
  attest Customer access and handling suitability; Mist Service cannot prove
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
- Initial API-versus-worker command races, bounded hand-off and delayed recovery
  tests proving that one engine effect cannot be reported as both success and
  failure, while a stopped API remains recoverable without manual intervention.
- PostgreSQL lock-mode and deadlock-victim tests proving that workflow actor and
  request-detail reauthorisation remain stable while notification recipient
  foreign keys are projected concurrently, with only a bounded idempotent
  command retry.
- Analyst clarification scope, repeated-loop, same-assignment, competing-open and
  process-version tests.
- Structured-conversation audience, direct-identifier, pagination, revocation,
  notification minimisation and unknown-type fail-closed tests.
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
- Mixed package order and checksum tests; covering-note version invalidation;
  malformed, animated, excessive-dimension and deceptive-image tests; distinct
  QC reviewer/releaser concurrency and one-person-team denial tests.
- External-link scheme, credential, fragment, private-host, allow-list, expiry,
  no-fetch and authenticated-redirect tests.
- Object-store and scanner interruption, quarantine, cleanup and joined restore
  rehearsals.
- Backup restore and recovery-point verification before pilot exit.
- Customer/staff context isolation, cache clearing, deep-link, CSRF, role-change
  and stable-identity self-request conflict tests, including PostgreSQL races
  proving a context switch and authenticated mutation have one serial order,
  plus context-namespaced notification suppression so Customer preferences
  cannot disable staff review, release or assignment alerts.

Authenticated polling is not evidence of human presence. Session validation is
read-only, while a CSRF-protected and browser-throttled activity endpoint is the
only path that advances idle state. The client also applies the absolute and idle
deadlines locally and broadcasts sign-out state between tabs. CSRF bootstrap is
stable for the opaque session so one tab cannot invalidate another tab's token.

Public login attempts consume independent opaque source and normalised-identifier
budgets before password verification. This retains brute-force protection across
replicas without a shared global exhaustion switch and without exposing a named
account to attacker-triggered hard lockout. Real and unknown identifiers follow
the same verification and public-error path.

### Pre-release product inspection and mixed-version packages

- Exact external destinations are returned only to the current draft author, exact
  claimed lead reviewer, or exact claimed QC reviewer/releaser. Customer and route
  projections omit both the destination and the inspection URL.
- Clean managed files are streamed through an authenticated no-store endpoint with
  `nosniff`, a sandbox content policy and a constrained disposition. Unknown, denied,
  unavailable and successful attempts create content-free access audit records.
- Membership expiry, team removal, Manager-position downgrade, assignment change,
  task reassignment, account disablement and self-request conflict are evaluated at
  access or mutation time. Login-time organisation snapshots are not sufficient.
- Package policy version is immutable. Existing rows remain version 1, new rows use
  version 2, and unsupported versions fail closed at artefact and submit boundaries.
- A dual-eligible stable account must be in effective Customer context to retrieve
  its own released product. The SQL entitlement accepts eligible staff identities
  but still requires active account, exact requester ownership, completed request,
  matching dissemination checksum and non-withdrawn release state.

### Migration and rollback integrity

- Context migrations are exercised against disposable PostgreSQL databases with
  populated pre-migration records. SQLite and migration-source inspection cannot
  establish backfill, trigger, constraint or downgrade behaviour.
- The mandatory PostgreSQL CI lane fails if this assurance test skips. Local runs
  without an authorised disposable PostgreSQL service may skip without weakening
  the release gate.
- Customer and Staff key collisions are created before downgrade so the selected
  retention policy is proved. Staff preferences and saved views survive; their
  colliding Customer variants do not.
- A downgrade past 0046 loses package policy pins. A later upgrade assigns all
  retained packages policy 1, so operators must not describe this as reversible.
- A downgrade past 0044 destroys conversations, delivery evidence, covering notes
  and context state. Recovery requiring those records uses a verified backup or
  roll-forward, not schema downgrade.
- Active QC backfill and inactive-account exclusion are asserted separately. The
  downgrade removes only migration-owned memberships and retains the stable QC
  organisation unit.
