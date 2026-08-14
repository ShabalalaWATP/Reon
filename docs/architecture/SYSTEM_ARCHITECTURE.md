# ISTARI Service system architecture

Status: current executable architecture and explicit deployment boundaries
Last reviewed: 14 August 2026

## 1. Purpose and scope

ISTARI Service is a human-led service-request application. A Customer submits a
structured request, authorised routing users select each organisational
destination, a Team Manager assigns one accountable Lead and additional
Analysts, and separate members of a combined QC Team review and disseminate the
product. The Customer then accepts delivery. Camunda coordinates human user
tasks. It does not make priority, route, assignment, approval or release
decisions.

This document describes the executable React, FastAPI, PostgreSQL and Camunda
system. The organisation model is in
[Organisation and routing](ORGANISATION_AND_ROUTING.md). Detailed decisions are
in the [architecture decision record index](../adr/). The complete process is explained in
[Workflow and Camunda](WORKFLOW_AND_BPMN.md). Production gaps remain authoritative in the
[gap register](../ENTERPRISE_READINESS_GAP_REGISTER.md).

This guide can be read at two levels. Sections 2 to 4 explain the shape of the
system in language suitable for product and delivery stakeholders. Sections 5
onwards give developers, security reviewers and operators the transaction,
failure, trust and scaling detail needed to change or run it safely.

## Contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [System context](#2-system-context)
3. [Executable components](#3-executable-components)
4. [Authorities and consistency](#4-authorities-and-consistency)
5. [Core data flows](#5-core-data-flows)
6. [Configuration sealing and routing](#6-configuration-sealing-and-routing)
7. [Startup and background processing](#7-startup-and-background-processing)
8. [Bounded read projections](#8-bounded-read-projections)
9. [Authentication and session controls](#9-authentication-and-session-controls)
10. [Trust boundaries](#10-trust-boundaries)
11. [Health, failure and recovery](#11-health-failure-and-recovery)
12. [Scaling and capacity](#12-scaling-and-capacity)
13. [Backup and disaster recovery](#13-backup-and-disaster-recovery)
14. [Deployment boundaries](#14-deployment-boundaries)
15. [Design and quality principles](#15-design-and-quality-principles)

## 2. System context

![ISTARI Service system context](../assets/architecture/01-system-context.svg)

The browser calls FastAPI only. It never calls Camunda or PostgreSQL. Application
code never reads Camunda-owned database tables. The local Compose deployment
shares one PostgreSQL server but creates separately owned application and
Camunda databases; that co-location is not a production recommendation.

The people on the left use one product. They do not need separate Camunda,
database or storage accounts to perform ordinary application work. The services
on the right sit behind the application boundary and are reached only through
supported, validated interfaces.

## 3. Executable components

![ISTARI Service container view](../assets/architecture/02-container-view.svg)

The word **container** here means a separately running application or data
service, not simply a Docker image. The same logical boundaries must remain when
the deployment technology changes.

### React web application

The Vite/React/TypeScript application is in `apps/web`. React Router controls
navigation, TanStack Query owns server state, and feature folders contain pages
and focused presentation components. `lib/api` is the browser's typed transport
boundary. `lib/auth`, route policy, capabilities and status helpers keep shared
concerns out of feature pages.

The production image currently uses a small Nginx server that serves static
assets, applies browser security headers, forwards `/api/` to FastAPI and
supports client-side routing. That Nginx configuration recognises only local
hostnames and is part of the local topology. It is not the target ingress or TLS
termination design.

An authenticated account has an explicit `CUSTOMER` or `STAFF` context. The
application shell derives navigation and route access from that context. A
context switch is a server mutation which rotates session and CSRF material,
advances a session generation and clears context-scoped TanStack Query state.
The browser never treats a visual role label as authority.

### FastAPI application

`apps/api/src/istari_service` is composed in `main.py`:

- `routers/` handles HTTP translation and dependencies;
- `schemas/` validates API requests and responses;
- `services/` coordinates application use cases;
- policy and projection modules contain framework-independent business rules;
- `repositories/` implements PostgreSQL reads and writes;
- `workflow/` adapts the Camunda V2 API to the internal workflow port;
- product storage, scanning and link-policy adapters implement product ports;
- maintenance, retention, restore verification and telemetry support operators.

`worker.py` is a separate executable composition root. Named PostgreSQL leases
fence singleton projection jobs, while existing row-level outbox leases permit
bounded parallel dispatch. A durable content-free heartbeat makes missing or
stale maintenance visible to API readiness.

The same fenced worker enriches transactionally created request-search
projections with 384-dimension FastEmbed vectors. The model is revision and
checksum verified at image build and opens in offline-only mode at runtime.
Embedding failure leaves full-text matching available and never blocks request
submission or human routing.

FastAPI applies body-size limits, trusted-host validation, restricted CORS,
security headers and correlation-aware telemetry. Authorisation is evaluated on
the server at role, operational-scope, object, assignment and transition levels.
Hidden navigation is never treated as a security control.

Core request and active-work services use typed, immutable domain decisions for
named operations such as view, cancel, feedback, claim, complete and routing
options. The decision may retain an internal denial category for tests and
diagnostics, but public request/work endpoints conceal role, route, ownership
and assignment denials behind the same `404 NOT_FOUND` response as an unknown
identifier. An authorised assignee attempting an action that is invalid for the
current workflow state still receives the existing conflict response.

This service-level policy is not the only control. PostgreSQL repositories also
scope request and work lookups by the authenticated identity, current role,
route membership, exact team and task assignment as applicable. Both layers are
required: query filtering minimises data retrieval, while the domain decision
protects each use case if an adapter returns a broader record than expected.

Executable architecture fitness tests protect these boundaries. Framework-free
policy cannot import FastAPI, SQLAlchemy or Camunda. Business route handlers
cannot contain SQL or branching workflow logic. Services cannot construct SQL
expressions, and repositories cannot depend on FastAPI or the Camunda SDK.

### PostgreSQL application database

PostgreSQL is authoritative for accounts, password/session state, request and
form content, configuration revisions and pins, organisational projection,
assignments, typed conversations and read state, product packages, acceptance,
feedback, notifications, board work packages, analytics facts, audit history and the requester-facing workflow
projection. It also owns the route-scoped related-request search projection:
weighted generated `tsvector` data is indexed with GIN, bounded narrative
similarity uses `pg_trgm`, and optional semantic retrieval uses an HNSW pgvector
index. Candidate retrieval and comparison reapply object and route membership
before bounded evidence is returned. Alembic owns schema evolution.

Local Compose separates identities:

- a bootstrap superuser creates databases and roles;
- a migration owner applies Alembic and grants;
- the API runtime role reads and writes ordinary application data;
- a read-only backup role runs `pg_dump`;
- the Camunda role is limited to the Camunda database.

### Camunda 8.9

Camunda is authoritative for process position and user-task lifecycle. The BPMN
contract is `workflow/service-request.bpmn`. Candidate groups and assignees are
calculated by FastAPI from server-owned configuration, then sent as opaque
workflow variables. Request text, products, reasons, session data and CSRF data
never enter Camunda.

The client currently supports `NONE` and `BASIC` authentication only. Local
Compose forces `NONE` and publishes the API to host loopback. This is acceptable
only for isolated development. Production OIDC integration and application
bootstrap are not implemented.

See [Workflow and Camunda](WORKFLOW_AND_BPMN.md) for every human task, outcome,
information loop, rework loop and end state.

### Product storage and malware scanning

In local mode, a private named volume backs a filesystem object-storage adapter.
Uploads are quarantined, bounded by file and package limits, streamed to ClamAV,
and promoted only after validation. Download is authorised through FastAPI; the
volume is never web-published. HTTPS external-product links are restricted to an
allowlist.

The local filesystem adapter also owns a small SQLite quarantine index used to
recover interrupted file transfers. It is an implementation detail of that
adapter, not a second application database. Request, identity, conversation,
package, workflow and audit data remain exclusively in PostgreSQL.

The application deliberately refuses to construct this local product runtime in
`prod`. No S3, GCS or other approved production object-store adapter, semantic
content-disarm-and-reconstruction service, lifecycle policy or key integration
exists in this repository.

Managed-product transfer is composed from focused grant, content-transfer and
scan/promotion coordinators. One shared transfer runtime owns the session
factory, storage, scanner, audit, quarantine cleanup and lease recovery.
External storage and scanner calls remain outside database transactions. The
public facade preserves the route contract while keeping these reasons for
change separate.

Configuration lifecycle uses the same restrained pattern. Draft, validation,
review and activation commands are separate use cases using focused ports. They
share repository, settings, event-publishing and clock contracts so audit and
transaction ownership do not drift between phases.

### Current technology baseline

| Layer | Current technology |
|---|---|
| Browser | React 19.2, React Router 8, TanStack Query 5, React Hook Form 7, Zod 4 |
| Web build | TypeScript 5.9, Vite 7, Vitest, Testing Library, Playwright, Nginx |
| API and worker | Python 3.12+, FastAPI 0.116+, Pydantic 2, SQLAlchemy 2 async, asyncpg, Alembic |
| Workflow | Camunda 8.9 and Camunda Python SDK 9, BPMN 2.0 contract |
| Application data | PostgreSQL 17, pgvector 0.8, `pg_trgm`, full-text search |
| Product boundary | Private filesystem adapter for local use, ClamAV 1.5, Pillow validation |
| Toolchain | Node.js 22+, pnpm 11, `uv`, Ruff, MyPy, ESLint and Prettier |

Manifests define supported ranges and lockfiles pin reproducible dependency
graphs. Containerfiles and `docker-compose.yml` define the executable local
runtime rather than this table.

## 4. Authorities and consistency

| Concern | System of record | Consistency rule |
|---|---|---|
| Human task position and lifecycle | Camunda | Reconciled into PostgreSQL |
| User, role, scope, active state and effective workspace membership | PostgreSQL | Checked at every protected boundary |
| Lead and Contributor participation | PostgreSQL | One active Lead, up to ten Contributors, exact delivery team |
| Request content and immutable revision | PostgreSQL | Submission transaction pins a revision |
| Organisation and workflow template | Sealed PostgreSQL configuration revision | Request pins the active revision at start |
| Human decision and reason | PostgreSQL audit event | Append-only, prior-hash linked |
| Product bytes and quarantine state | Storage adapter plus PostgreSQL metadata | Promote only after scan and state checks |
| Dashboard/request status | PostgreSQL projection | Never invent progress when Camunda is unavailable |
| Feedback | PostgreSQL | One accepted record per completed request |

PostgreSQL and Camunda cannot participate in one atomic transaction. The system
therefore favours durable intent and convergence over a distributed transaction.

Request and administrative audit hash input uses immutable named records.
Request audit details accept forward-compatible keys but recursively constrain
depth, collection size, key shape, text length and JSON value types before
hashing and persistence. Workflow-start outbox commands likewise use one
validated serialisation and parsing type before the worker contacts Camunda.

## 5. Core data flows

### Submit and start

1. The browser sends a validated form, session cookie, CSRF token and duplicate-
   submission key to FastAPI.
2. FastAPI authenticates the Customer, verifies ownership and validates all
   mandatory fields.
3. One PostgreSQL transaction stores the immutable submitted revision, pins the
   active sealed configuration and inserts a start command in the outbox.
4. The worker commits a fenced claim, sends the command to Camunda without an
   open database transaction, then opens a new transaction to finalise it using
   the stable request business identifier.
5. Camunda creates the process instance or reports a conflict. Conflict recovery
   searches by business identifier and verifies the exact process definition.
6. PostgreSQL records the process identity and projected task. Until that proof
   exists, the request remains pending rather than actionable.

### Human task action

1. FastAPI validates the actor, scope, assignment, expected version and allowed
   transition in PostgreSQL.
2. A first transaction stores recoverable command intent, audit context and a
   fenced owner/generation claim, then commits.
3. The dispatcher performs the Camunda claim or completion without holding a
   PostgreSQL connection or row lock.
4. A new finalisation transaction reauthorises the actor and object, compares
   the exact owner/generation, records the result and updates the projection.
5. If Camunda is unavailable or its search view lags, leases expire safely and
   reconciliation proves the actual task/process state before recovery.

### Action links and operational navigation

PostgreSQL projects a content-minimised **My actions** register from the
authoritative request event chain. The projection is a locator, not a workflow
authority. Unclaimed candidate work is marked `SHARED`; a successful Camunda
claim causes the next atomic request-event projection to address only the named
assignee and mark it `PERSONAL`.

Customer actions link to the Customer request page. Staff actions link to the
appropriate CRIOC, command, Ops, Team Manager, Team Analyst or QC queue with the
request UUID as a selector. `GET /work-items?requestId=...` applies that selector
inside the existing actor-scoped task query. A copied UUID therefore cannot
broaden access. A missing, completed or differently assigned task returns no
row, and the frontend reports that the action ended instead of selecting the
first item in the queue.

The navigation separates personal work from shared unit work:

- **My assigned actions** is the sidebar route to the personal and explicitly
  shared action register;
- the organisation-named workspace, such as **CRIOC workspace**, contains the
  actionable unit queue, people, calendar, statistics and activity;
- standalone purpose-named queue routes remain compatible with notification and
  bookmarked deep links, but are not duplicated in the sidebar when a current
  workspace exists.

These are staff concerns. Customer primary navigation contains only **My
requests** and **New request**. Customers are route-gated away from the personal
calendar and organisation directory as well as having no link to either page.
Their profile remains available through the account menu.

### Clarification

An assigned Analyst may request information from the Customer. PostgreSQL stores
the question and full history; Camunda moves to the requester task. The response
returns work to the same Analyst. Routing organisations observe progress but do
not approve the delivered product.

### Request conversations

Conversation messages are distinct from workflow clarification. An authorised
participant chooses one server-calculated target: Customer, current owner, Team
Managers, assigned Analysts, a routing unit on the selected path, or the combined
QC Team. PostgreSQL records the immutable message, author, active identity
context, target, visibility, time and read state. Customer-visible and staff-only
audiences are enforced by the query and policy boundary. A message can inform or
ask a question, but cannot transfer ownership or advance Camunda.

### Organisation workspaces and assignment

Every organisation unit has an effective-dated workspace roster. The global
representative role controls workflow eligibility, while the independent
Manager or Member position controls exact-unit stewardship. A Manager may
maintain Members and unit calendar events. Every Member may record their own
leave, courses, training and availability. Only delivery-team Managers can
create request-linked commitments, assign one accountable Lead and up to ten additional Analysts,
or use board, iteration and capacity controls. Routing Managers and Members both
claim their own routing task and neither creates an extra approval step.

Participant history remains in PostgreSQL. The active Lead is sent to Camunda as
the accountable task assignee, while every currently assigned Analyst has the
same permitted production controls through object-level FastAPI policy. The Lead
badge therefore communicates accountability rather than elevated functionality.

The same policy boundary permits a current Manager membership to read active and
terminal requests assigned to that exact delivery team. This keeps the team's
Board history inspectable without extending visibility to ancestors, siblings or
other teams. PostgreSQL membership, effective dates and assigned-team identity
are rechecked for every detail read.

### Product lifecycle

1. Any currently assigned Analyst creates an attributable draft package and
   opens upload intents with bounded metadata.
2. A short metadata transaction commits an operation lease. Bytes then enter a
   private quarantine location and are size checked without retaining that
   transaction.
3. The scanner inspects the complete object outside PostgreSQL. Failed or
   unavailable scanning does not release the product.
4. A clean artefact is promoted, then a new fenced transaction reauthorises and
   associates it with the package revision.
5. The author orders one to ten managed PDF, DOCX, PPTX, JPEG or PNG files and/or
   allowlisted HTTPS links, adds the required covering note and freezes the
   package for review.
6. A Team Manager reviews it. A QC Team Manager then performs quality review and
   a different QC Team Manager claims release, preserving separation of duty.
7. Dissemination makes the exact approved artefacts and covering note visible to
   the owning Customer dashboard.
8. File download rechecks request ownership and product release state, commits
   access metadata, closes the session, then streams through FastAPI.
9. The Customer explicitly accepts delivery and may submit the single feedback
   record.

## 6. Configuration sealing and routing

Organisation changes are effective-dated revisions, not in-place edits to a
request's route. A proposer creates and validates changes. A different authorised
actor approves the canonical digest. Activation materialises the sealed snapshot
and readiness verifies its integrity. New requests pin the active revision;
existing requests retain their original names, codes, hierarchy, staffing and
workflow template.

Routing selection returns only the selected path and authorised direct children.
Search is literal name/code filtering within those children, not global
enumeration or automated recommendation. FastAPI validates the destination again
when the action is submitted.

## 7. Startup and background processing

One managed workflow-runtime adapter creates the Camunda SDK client from
validated settings, enters it, wraps it behind the `WorkflowEngine` port and
guarantees client shutdown. Both application startup and the independent worker
depend on that context-managed port rather than constructing the SDK directly.
Startup fails closed if client entry or adapter construction fails. Credentials
remain inside the outer adapter and are not copied into application state.

Application startup restores or seeds the active configuration projection and
seeds synthetic accounts only when explicitly allowed. It starts no maintenance
loop. The separate `istari-worker` executable coordinates:

- process-start outbox dispatch;
- human workflow-command dispatch;
- workflow projection reconciliation;
- notification projection reconciliation when enabled;
- leases, bounded retry and health state.

Each singleton job has an expiring named lease, owner and monotonically
increasing generation. Long jobs renew their lease. A stale worker cannot record
success after takeover, and one job failure does not stop later jobs. Local
Compose runs one worker; multiple replicas are safe but still require a measured
connection budget. Alembic remains a one-shot release job, never API or worker
startup work.

## 8. Bounded read projections

Customer requests and drafts, staff work, routing tracking, administrator users,
request history and Board items use opaque keyset cursors. Leading scope and
ordering columns have matching PostgreSQL indexes. Board search and filters run
in SQL, with each applicable source reading at most `limit + 1` candidates
before a bounded merge. The browser appends pages and resets the cursor when a
filter changes. Cursors contain ordering keys only and never grant authority.

Team workspaces compose several independently authorised bounded projections.
Delivery-team Overview combines exact-team Board totals, current membership,
calendar occurrences and recent activity. Routing-unit Overview combines a
unit-scoped human decision queue with its calendar and activity. The full
actionable queue is embedded as a unit-scoped workspace view. The Board reads a
workflow-derived Service Request board and a separately collapsible internal
Work Package board. A failed source is labelled and does not widen another
source's scope.

The delivery Board returns two distinct facts: a cursor-bounded item page and
complete per-column aggregates for the same search, type, priority, owner and
due-date predicates. Active delivery lanes are shown first. Downstream,
exception and terminal lanes remain explicitly expandable. Request cards are
workflow projections and can change stage only through named Camunda actions;
work packages use their own reasoned, versioned planning transitions.

Current team membership exposes bounded, self-declared operational skill labels
from the user's profile. These labels support human allocation only. They carry
no proficiency, ranking, endorsement or automated assignment semantics.

The People register links to a separate exact-team colleague projection. It
combines professional account information with the relevant membership but
deliberately omits service number and free-form profile notes. Both the viewer's
workspace access and the subject's membership history are checked before any
profile is returned.

Task hasteners reuse two durable projections. FastAPI first confirms a current
Manager position, locks and refreshes the request, then confirms the exact
assigned delivery team and resolves the active Lead and Contributors from
PostgreSQL. It appends an unchanged-status event to the request's tamper-evident
history and projects content-minimal notifications to those Analysts. The direct
`TASK_HASTENER` event is mandatory even when a recipient has disabled general
assignment notifications, and the transaction succeeds only when every resolved
recipient is projected. No Camunda command is emitted because a hastener
communicates urgency without changing workflow state or ownership.

Hasteners are accountable request history, so every user already authorised for
the request, including its Customer, sees the same event. Notification links use
an exact-team board-request endpoint that bypasses list filters, pagination and
hidden lanes while repeating object-level workspace authorisation.

## 9. Authentication and session controls

The current application uses database accounts, Argon2 password hashes, opaque
server-side sessions in an HttpOnly cookie, CSRF binding, absolute and idle
expiry, active-account checks and a short session-bound step-up window for
privileged administration. The shared `admin` password is allowed only for
synthetic local fixtures.

Before account lookup or Argon2 verification, login consumes atomic global and
source-specific capacity in PostgreSQL. The source is stored as a one-way
digest, forwarded addresses are accepted only from configured proxy CIDRs, and
each API process bounds concurrent Argon2 operations. This makes the resource
budget shared across replicas without changing the local fixture identity
contract. A managed edge limiter remains required for volumetric defence.

This is not a production identity design. There is no OIDC login/callback,
claims-to-role bootstrap, MFA integration, identity-provider logout, service
account model, PAM or break-glass procedure. `ENVIRONMENT=prod` rejects demo
accounts and insecure cookies but cannot make the missing identity integration
exist.

Accounts may be provisioned with both Customer and Staff capability. The active
context is stored server-side and returned with available contexts in the session
view. A switch rotates the session identifier and CSRF proof, increments the
generation used in protected query keys and redirects to `My requests` or Staff
`Home`. Self-request conflict policy prevents Staff authority being used on the
same person's Customer request.

Password assistance is deliberately administrative rather than self-service in
the MVP. The public endpoint always returns the same accepted response. It
normalises and matches an active account inside a bounded transaction, records
only a one-way source key plus an optional matched-user identifier, and sends a
mandatory in-app account-security notification to every active Platform
Administrator. Per-source, per-account and global limits constrain abuse without
revealing whether an account exists.

The platform classification is a versioned singleton in PostgreSQL. Every page
reads its public, content-free value and defaults visually to `OFFICIAL` while
that read is pending. Only a Platform Administrator with CSRF and fresh step-up
may change it, using optimistic version matching and the administration audit
chain. This strip is a global visual marking, not an information-authorisation
label and not a substitute for object-level access control.

## 10. Trust boundaries

1. **Browser to web/API:** untrusted input, cookies, CSRF, XSS and origin checks.
2. **API to PostgreSQL:** parameterised SQL/ORM, least-privileged runtime role,
   migrations kept separate.
3. **API to Camunda:** external-effect boundary with authentication, TLS and
   contract validation required in a connected target. One managed runtime owns
   SDK construction and shutdown for API and worker processes; neither entry
   point may import the SDK directly.
4. **API to product/scanner:** hostile files remain quarantined until scanning;
   fail closed on scanner error. Clamd is internal-only and reads definitions
   from a read-only mount. A separate updater that never receives submitted files
   owns the writable volume and outbound mirror network.
5. **Operator plane:** migration, BPMN deployment, attestation, backup and
   recovery require separate audited authority.
6. **Configuration approver:** separation from proposer; the shared runtime
   credential is not sufficient production proof of a human signature.

## 11. Health, failure and recovery

`GET /health` is process liveness and contains no dependency details. `GET
/ready` checks PostgreSQL, Camunda, sealed-configuration integrity and the
durable worker heartbeat when required; it returns HTTP 503 when a required
check is unavailable.
Operational snapshots expose content-free counts and age thresholds.

Expected failure behaviour:

- PostgreSQL failure makes readiness fail and prevents state-changing work.
- Camunda failure leaves durable commands pending and makes readiness fail.
- Scanner failure prevents managed-file release.
- Invalid configuration sealing makes readiness fail closed.
- Exhausted workflow recovery becomes visible support work; state is not guessed.
- Browser/API failures preserve draft or committed server state and show an error.

See [support and incident response](../operations/SUPPORT_AND_INCIDENT_RUNBOOK.md),
[backup and restore](../operations/BACKUP_RESTORE_AND_MAINTENANCE.md) and
[continuity](../operations/BUSINESS_CONTINUITY_AND_DISASTER_RECOVERY.md).

## 12. Scaling and capacity

The async PostgreSQL pool is configured per API process. The connection maximum
is approximately `replicas × (DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW)`, plus
migration, backup and operator connections. It must remain below the managed
database budget. Worker connections have their own pool and overflow settings,
so add `worker replicas × worker connection maximum` to that calculation.
Named-lease contention and Camunda rate limits must be validated at target scale.
Login capacity is shared in PostgreSQL, so the global limit does not multiply
with API replicas. The per-process Argon2 concurrency value does multiply and
must be included in CPU and database-capacity tests.

Static web assets may be cached at an ingress or CDN only after cache policy is
reviewed. Authenticated API and product responses must not be publicly cached.
Product streaming and malware scanning need independent throughput, temporary-
storage and timeout budgets. Camunda partition, broker and replica sizing must
follow its supported production architecture rather than the single local
container.

## 13. Backup and disaster recovery

Application recovery requires coordinated evidence for PostgreSQL, Camunda and
product objects. Local scripts create and verify a PostgreSQL custom-format dump,
checksum, catalogue, Alembic revision and audit chains, but Compose volumes are
not backups. A production plan must define PITR, encrypted immutable copies,
Camunda-supported backup, object versioning, restoration ordering, reconciliation,
RPO/RTO and regular isolated exercises.

Restoring only PostgreSQL may leave workflow position or product bytes missing.
After restoration, keep ingress closed, verify schemas and audit chains, restore
the other authorities, attest the deployed process, reconcile active requests,
then obtain incident authority before reopening.

## 14. Deployment boundaries

Host preparation for Windows, macOS and Linux is in
[Workstation and Linux host setup](../deployment/HOST_SETUP.md). The supported
repository path is [local Docker](../deployment/LOCAL_DOCKER.md).
Private [AWS](../deployment/AWS_SANDBOX.md),
[GCP](../deployment/GCP_SANDBOX.md) and
[Azure](../deployment/AZURE_SANDBOX.md) host procedures are synthetic sandbox
patterns using encrypted management tunnels, not production designs. The
[Kubernetes target](../deployment/KUBERNETES_TARGET.md) is explicitly
unimplemented: there are no application manifests, Helm values, infrastructure
as code, OIDC bootstrap, production object-storage adapter or validated topology.

## 15. Design and quality principles

### Dependency direction

The delivery technologies depend on application rules. Application rules do not
depend on React, FastAPI, SQLAlchemy or Camunda.

```text
React features → typed API client → FastAPI routes
                                      ↓
                              application services
                                      ↓
                              domain policy and rules
                                      ↑
                     ports ← PostgreSQL and Camunda adapters
```

This is pragmatic SOLID design rather than a requirement to create a class or
interface for every function:

- routes translate HTTP and delegate;
- services coordinate one use case and its transactions;
- policy modules return typed permission and transition decisions without
  importing FastAPI, SQLAlchemy or Camunda;
- repositories translate between application concepts and PostgreSQL;
- adapters isolate external systems whose contracts can fail or change; and
- React components focus on rendering and interaction while API clients and
  hooks own server communication.

The editable [Structurizr workspace](structurizr/workspace.dsl) contains system,
container, component, dynamic request-delivery and deployment views. It is the C4
model for these boundaries; the curated SVGs are the Markdown presentation set.

An abstraction is introduced when it protects a real boundary, such as storage,
workflow, identity, scanning or persistence. It is not introduced merely to make
the directory tree look layered.

### Interface principles

- Use a calm, readable operational layout with clear status and ownership.
- Separate personal workload from organisation workload.
- Name navigation by the task a user is trying to perform.
- Show loading, empty, success, denied, conflict and recoverable-error states.
- Keep keyboard focus, labels, contrast and reduced motion at WCAG 2.2 AA.
- Use charts only when the visual adds meaning, and provide an accessible table
  with the same facts.
- Do not expose engine identifiers or implementation terms where plain English
  explains the action.

### Data and audit principles

- Drafts remain private and do not start Camunda.
- Submission creates an immutable revision and durable process-start intent.
- Later information appends history rather than rewriting submitted evidence.
- Expected versions reject stale or duplicate mutations.
- Workflow and administrative changes record attributable, prior-hash-linked
  audit events.
- Pending external work stays explicitly pending. The application never guesses
  a successful workflow position.

### Quality principles

- Backend and frontend application code each maintain at least 95 per cent line
  and branch coverage.
- Hand-written source files remain at or below 350 lines. Markdown documentation
  is exempt so one coherent authority does not become several fragments.
- Static typing, lint, formatting, dead-code, dependency, licence, secret,
  container and documentation checks run in CI.
- Security-sensitive work updates the applicable threat model.
- Material architecture changes update or add an ADR.
- Operational procedures are tested on synthetic environments and their dated
  result is stored separately from the current procedure.

### Change rule

Add a dependency or layer only when it materially improves correctness,
security, maintainability or delivery risk. Keep the current guides factual and
plain. Put chronology in the [development story](../DEVELOPMENT_STORY.md),
decision context in an ADR and executed evidence in `docs/assurance/`.
