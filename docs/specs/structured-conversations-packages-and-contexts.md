# Structured conversations, managed packages and bounded contexts

## Status

Implemented and runtime-verified product and security contract, 14 August 2026.
Automated unit, authorisation and contract evidence is complemented by a real
disposable PostgreSQL migration round trip and a complete Chromium journey. The
journey verified bounded Customer and staff contexts, audience-isolated
conversation history, managed multi-file package production, distinct Manager
and QC review, separate release authority, Customer retrieval and acceptance.
These executable runtime gates remain mandatory release evidence and are not
replaced by source inspection.

## Purpose and existing authorities

This amendment gives authorised participants one structured way to discuss a
request, packages several safe product artefacts under one covering note, keeps
quality review and release attributable to different people, and supports users
who hold both Customer and staff responsibilities without combining those
authorities.

The following documents remain authoritative and are not replaced:

- `route-monitoring-and-coordination.md` and ADR 0032 own exact-route monitoring,
  non-blocking coordination and upstream return requests;
- ADR 0010 owns the workflow-blocking Analyst clarification loop;
- `operational-product-evolution.md`, `managed-product-upload-hardening.md` and
  ADR 0016 own quarantine, immutable package versions, scanning, private storage,
  authenticated dissemination and approved external links;
- ADR 0033 owns shared assigned-Analyst production authority;
- `routing-workspace-monitoring-and-customer-acceptance.md` and ADR 0034 own
  post-dissemination Customer acceptance; and
- current session, role and object-level access policies remain authoritative
  for authentication and request access.

Where this amendment is narrower, the narrower disclosure and separation rule
applies.

## Outcomes

1. A request has a paginated, append-only conversation made from typed entries
   with explicit visibility, authorship and relationship to workflow state.
2. A managed release package can contain a covering note and several independently
   validated files, safe images or approved external links.
3. A combined QC Team can contain several Managers, but the person who records
   QC review cannot release the same immutable package version.
4. A user who may act as both a Customer and staff member selects one bounded
   context at a time. Every request and command is authorised in that context.
5. A staff member cannot use Customer context to create a request that they can
   route, assign, review or release through their staff authority.

## Structured request conversation

### Entry types

The conversation presents related records in one chronological interface while
retaining their different domain meanings:

| Entry | Purpose | May change workflow state |
| --- | --- | --- |
| Customer message | Non-blocking information or question addressed to authorised staff | No |
| Staff response | Non-blocking response explicitly addressed to the Customer | No |
| Internal coordination | Staff discussion for the current owner or selected route | No |
| Clarification request or response | Existing versioned, workflow-blocking exchange | Only through the existing clarification command |
| Return request and response | Existing accountable request to an upstream owner | Only the existing adjacent workflow return command may move work |
| System lifecycle entry | Content-minimised summary of an authorised state change | It reports a change made elsewhere |

Free-form text is never inferred from a workflow event or notification. A
conversation entry stores its own stable identifier, request identifier, type,
author, audience, creation time and body. Reply relationships may form one level
of contextual threading, but pagination remains chronological and bounded.

### Visibility

Audience is an explicit server-owned enum, not a client filter:

- `CUSTOMER_AND_STAFF`: the originating Customer and staff who currently hold
  request access;
- `CURRENT_OWNER`: staff in the exact current owning unit and specifically
  assigned participants where the workflow stage permits it;
- `SELECTED_ROUTE`: current members of units recorded on the immutable selected
  route, subject to the existing tracker exclusions; and
- `ASSIGNED_TEAM`: current Managers and assigned Analysts in the exact delivery
  team.

The persisted default is the narrowest staff-only audience. Creation commands
must explicitly select a supported audience, and the server rejects an audience
the actor cannot address. Read queries apply visibility before ordering,
pagination and cursor construction. Changing roles, route membership, team
membership, assignment, account state or active context changes live visibility
immediately without deleting history.

Customers do not receive internal coordination, staff notes, assignment reasons,
recipient identifiers, unreleased package metadata or pre-dissemination review
history. Route monitors receive only the lifecycle and coordination material
already permitted by the tracking contract. Notifications contain a safe entry
type and deep link, never the message body.

### Interaction and accessibility

- The composer labels the selected audience in plain language before submission.
- Internal and Customer-visible entries have distinct text labels as well as
  colour treatment.
- The interface supports keyboard composition, visible focus, announced send
  errors and a reduced-motion update state.
- Empty, loading, permission-loss, stale cursor and retry states are explicit.
- A failed send remains in local draft state and is never displayed as persisted.
- Conversation export and retention follow request-content policy, including
  legal hold and tamper-evident event evidence where applicable.

## Managed release package amendment

### Package envelope

One immutable package version contains:

- a required Customer-facing title;
- a required covering note of 20 to 4,000 characters;
- one to ten ordered artefacts; and
- package version, author, checksum manifest and lifecycle evidence.

The covering note is part of the reviewed package version. It is not an internal
conversation message and is not visible to the Customer until dissemination.
Editing the note, order, label, file, image or link creates a new version and
invalidates prior Manager and QC decisions.

### Artefacts

Each artefact is independently one of:

1. a managed PDF, DOCX or PPTX file under the controls already specified by
   `operational-product-evolution.md` and ADR 0016;
2. a safe raster image in PNG or JPEG format; or
3. an approved external HTTPS link.

Safe images are treated as untrusted managed files, not inline HTML. The server
checks declared size, extension, media type, signature, bounded dimensions,
pixel count, frame count, metadata size and decoder completion before malware
scanning and promotion. SVG, animated images, executable metadata, polyglots and
decoder failures are rejected. Customer responses use an authenticated
application endpoint, `no-store`, `nosniff` and a safe disposition. The
application does not proxy, preview or fetch external links.

Every artefact has a bounded display label and optional Customer-facing note.
The aggregate enforces per-object, package, request, author and service quotas
before issuing an upload intent and again before finalisation. A package cannot
enter Manager review while an artefact is pending, quarantined, failed, expired,
withdrawn or missing current scan evidence.

### Legacy pinning

Existing plain-text deliverables and package versions retain the product mode,
artefact policy and workflow definition pinned when they were created. They are
not converted into multi-artefact packages in place. A request with any managed
package remains on the managed-product path and cannot fall back to a legacy
download. Enabling images or the new package envelope affects new package
versions only. In-flight versions complete under their pinned rules unless an
explicit, audited migration is separately specified and approved.

## Combined QC Team and separation of duties

The organisation contains one Combined QC Team with current QC Users and QC
Managers. Membership grants review-stage access to the QC workspace, not blanket
permission to perform every action. Only Managers hold release accountability.

The QC Team has a stable organisation identity for membership and audit
references, but it is a support unit outside the four-level request-routing
configuration. It is never offered as a routing destination or counted as a
command-level operational branch. Identity administration exposes that one
deterministic support unit only when creating or updating a Quality and Release
account; all other role-to-unit choices continue to require configured routing
units.

For each immutable package version:

1. a current QC User or QC Manager claims and records the QC review decision;
2. an approved version becomes release-ready;
3. a different current QC Manager disseminates it to the originating Customer,
   whom the server resolves from the request; and
4. final-boundary checks revalidate both actors, exact QC Team membership,
   package version, scan evidence, review state and the server-resolved Customer.

The reviewer and releaser identifiers must differ. Reassignment, account
deactivation or membership expiry removes live authority. A single-person QC
Team may review or return work but cannot release its own approval. The workspace
shows a factual `Awaiting independent releaser` state and operational alert. It
does not waive separation or borrow a Manager from another team.

Team Manager review remains a separate earlier decision and does not satisfy QC
review. Package authors and assigned Analysts cannot perform either QC action.
Customer acceptance remains separate and occurs only after dissemination.

## Bounded Customer and staff contexts

### Context selection

A user with both Customer and staff eligibility has one identity and session but
one active context. Context is a server-validated value bound to the session and
included in CSRF-protected context changes. It is not accepted from an arbitrary
request header.

- Customer context exposes only that user's Customer requests and actions.
- Staff context exposes only roles, organisation memberships, assignments and
  management grants effective for that user.
- Navigation, notification counts, saved views and caches are namespaced by
  context.
- Saved action views persist the stable identity and effective context together.
  Existing views are migrated to staff context, equal names may exist once per
  context, and cross-context update or deletion returns the ordinary not-found
  response.
- Notification preferences are persisted and evaluated by stable identity plus
  effective context and event group. Customer-context suppression applies only
  to Customer recipients, while staff REVIEW, RELEASE, ASSIGNMENT and other
  staff alerts use the independent staff preference. Customer-relevant groups
  remain configurable in Customer context, subject to mandatory-alert policy.
- A context change rotates context-bound authorisation state, clears protected
  client caches and revalidates the destination route.
- Every authenticated mutation locks and revalidates the server-side session
  context version in the same database transaction as its state change. A
  concurrent context switch therefore either waits for the authorised mutation
  to commit or makes the stale mutation fail before it can commit. Detached
  upload and scanning flows repeat this fence in each metadata transaction and
  never retain a database connection while streaming bytes.
- Deep links either open within the current authorised context or require an
  explicit context change. They never switch silently.

Audit evidence records identity, selected context and effective role for every
conversation, workflow, product-review and dissemination command. Context does
not add authority and cannot override object-level checks.

### Self-request conflicts

A request created by an identity in Customer context is marked with that stable
identity as its originating Customer. While it is active, the same identity is
excluded from staff actions on that request, including routing decisions,
ownership returns, team assignment, production participation, Manager review,
QC review and release.
It cannot be selected as a Lead or additional assigned Analyst.

The conflict follows identity, not username, active context or current role.
It is rechecked at every staff mutation boundary that references the request,
including work-package creation, editing, movement and reservations, calendar
commitments, task hasteners, conversations, related-record decisions and product
operations. The originating Customer cannot be selected as a package owner,
additional Analyst or calendar/reservation subject for their own request. Denials
use the ordinary not-found response and do not disclose that the request exists.

Notification projection, notification reads, action queues and direct request
detail also recheck current authority. Quality-review access requires any live
membership in the exact Combined QC Team; release-stage access requires a live
Manager position there. Role or scope alone is insufficient, and expiry,
revocation or deactivation removes references and deep links immediately. For
Analysts, the stored Lead field and a non-ended
participant row are accountability evidence only: action and notification reads
also require the participant assignment to be effective and a live Delivery
Specialist membership in the request's exact assigned team.
Later role or membership changes do not remove the self-request conflict. Queue projections omit the
conflicted action, and direct identifiers fail with the ordinary non-disclosing
denial. If staffing makes progression impossible, a different authorised person
must act or support must use a separately specified, audited reassignment process.

## Data and API boundaries

- PostgreSQL remains authoritative for conversation entries, audience, package
  envelope and manifest, review and release actors, context and audit.
- Camunda remains authoritative for workflow position and human task lifecycle.
- Object storage remains authoritative only for private quarantined and released
  bytes.
- React calls FastAPI only and treats server capabilities as authoritative.
- List and detail endpoints use bounded cursor pagination and reapply audience,
  context and object policy to every page.
- Mutation commands require expected versions and idempotency keys where a retry
  could duplicate a message, review, release or context transition.

## Rollout and compatibility

1. Add schema and API fields with staff-only defaults. Deploy tolerant readers
   before enabling writers.
2. Backfill only classification and pinning metadata proved from authoritative
   records. Do not reinterpret historical free text as Customer-visible content.
3. Keep the composer, safe-image type, package envelope, QC separation and
   context selector behind independently reversible server capabilities.
4. Enable Customer-visible reads before Customer writes, then staff writes,
   package creation, QC separation and context switching in controlled stages.
5. Preserve legacy request, deliverable and package routes until pinned records
   reach terminal retention states. Reject ambiguous fallback.
6. Rehearse rollback with mixed old and new records. Disabling a capability must
   block new commands without hiding authorised history.

## Observability and operations

Metrics and alerts are content-free and partitioned by capability and outcome:

- conversation append success, conflict, denial and projection lag;
- audience-filter denial and invalid-context counts;
- upload intent, scan, decoder, quarantine, promotion and cleanup outcomes by
  safe media class;
- packages waiting for Manager review, QC review and independent release;
- independent-release staffing shortfall age;
- context-change success, denial and session invalidation;
- self-request conflict denials; and
- outbox age, retry exhaustion and reconciliation drift.

Structured logs use correlation identifiers and safe enum values only. They do
not contain conversation bodies, covering notes, filenames, link destinations,
Customer identities, package content or session tokens. Dashboards distinguish
expected policy denials from dependency failures. Alert owners, thresholds and
runbooks are required before pilot enablement.

## Acceptance criteria

### Conversation and visibility

1. Each audience is exercised by list, detail, cursor and direct-identifier tests
   across Customer, owner, route, assigned team, unrelated user and Administrator.
2. An unknown or new entry type defaults to staff-only.
3. Membership, assignment, context and account revocation remove live visibility.
4. Notification, analytics and routine logs contain no conversation body.
5. Clarification and return commands retain their existing semantics.

### Package and release

6. Mixed packages preserve order and immutable checksums across safe files,
   images and approved links.
7. Malformed, oversized, animated, excessive-dimension, deceptive and unsupported
   images fail before review and leave no accessible object.
8. Editing the covering note or artefact creates a new version and invalidates
   Manager and QC decisions.
9. Customers and route monitors cannot infer an unreleased package, note, image,
   filename, link or review decision.
10. The QC reviewer cannot release the same version through stale, replayed,
    concurrent or direct commands.
11. A second eligible QC Manager can release the exact approved version, after
    which only the originating Customer can access and accept it.
12. Legacy records stay pinned and managed records never fall back to legacy.

### Context and rollout

13. Counts, navigation, caches and deep links cannot cross contexts.
14. A dual-eligible identity cannot perform staff action on its own request after
    switching context or changing role.
15. Context changes require trusted origin, CSRF, active session and server-derived
    eligibility.
16. Mixed-version rollout, capability disablement, outbox retry and rollback do
    not duplicate messages, reviews or releases.
17. WCAG 2.2 AA, independent 95 per cent line and branch coverage, ordinary p95
    latency and existing product security gates remain release requirements.

## Explicit exclusions

- Real-time chat, presence, typing indicators and unbounded threads.
- Customer access to internal coordination or pre-release product records.
- Automatic summarisation, routing, assignment, review or release.
- Fetching or previewing external links in the backend.
- Vector or animated images, archives, audio, video or arbitrary file types.
- Waiving reviewer and releaser separation for a one-person QC Team.
- Merging Customer and staff authorities into one ambient context.
- Exposing historical free text through retrospective reclassification.

## Managed-product inspection and compatibility clarification

- A draft author may inspect only their own clean managed files and exact approved
  destinations while their Analyst membership and assignment remain live.
- The exact claimed lead reviewer and the exact claimed QC reviewer or releaser may
  inspect the same checksum-bound artefacts only at their current workflow stage.
- Customer context, route monitoring and unrelated staff receive a non-enumerating
  response. Successful, denied and unavailable file-inspection attempts are audited
  without recording a filename, destination or content.
- Existing product packages are pinned to policy version 1. New packages are pinned
  to version 2. Version 1 retains its original no-covering-note submission contract
  and excludes image artefacts; version 2 requires a covering note and permits the
  current structurally validated JPEG and PNG types.
- Staff accounts explicitly switched to Customer context use the same originating-
  Customer product view, download and acceptance boundaries as Customer-only
  accounts. Stable staff authority is never available in that context.

## PostgreSQL migration acceptance

The 0043 to 0047 chain has an executable PostgreSQL round-trip gate. It starts
from revision `0043_security_event_dedup` with synthetic existing users,
sessions, requests, preferences, saved views, packages and active and inactive
QC accounts. It upgrades one revision at a time and proves the context,
managed-product and QC backfills against stored rows. PostgreSQL must reject
duplicate context keys, an unsupported package policy and a second delivery
read. Source-text inspection is not migration evidence.

The same gate introduces Customer and Staff records with colliding preference
groups and saved-view names, then downgrades one revision at a time. The asserted
loss policy is deliberate: colliding Customer rows are removed in favour of
Staff rows, package policy pins are removed, and the 0044 downgrade removes
conversation data, covering notes, product modes and session context. The QC
unit is retained while migration-owned memberships are removed. Re-upgrade must
recompute deterministic backfills, run `alembic check`, and a second disposable
database must prove an empty-to-head path. Both databases are removed after the
gate, including after a failed assertion.
