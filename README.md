# ISTARI Service

ISTARI Service is a secure, human-led request and delivery workspace. A Customer
submits a complete request through a structured form, authorised organisations
route it, a delivery team produces the work, a Team Manager and QC Manager check
it, and the Customer receives the released product in their dashboard.

The repository is deliberately safe for public source control. Its organisation,
people, requests and products are synthetic. It must not contain real operational
content, private service details, production credentials or classified material.

> **Current status**
> The complete local synthetic application runs with React, FastAPI, PostgreSQL,
> Camunda and ClamAV. It is suitable for development and controlled synthetic
> evaluation. It is not approved for real data or production use. The remaining
> production decisions are explicit in the
> [enterprise readiness gap register](docs/ENTERPRISE_READINESS_GAP_REGISTER.md).

![ISTARI Service system context](docs/assets/architecture/01-system-context.svg)

## Contents

1. [What the product does](#what-the-product-does)
2. [Who uses it](#who-uses-it)
3. [How a request moves through the service](#how-a-request-moves-through-the-service)
4. [What users see](#what-users-see)
5. [Architecture in plain English](#architecture-in-plain-english)
6. [Security and data protection](#security-and-data-protection)
7. [Repository structure](#repository-structure)
8. [Run the complete application locally](#run-the-complete-application-locally)
9. [Run from source](#run-from-source)
10. [Synthetic accounts](#synthetic-accounts)
11. [Configuration](#configuration)
12. [Testing and quality gates](#testing-and-quality-gates)
13. [Deployment choices](#deployment-choices)
14. [Documentation map](#documentation-map)
15. [Known production boundaries](#known-production-boundaries)
16. [Working on the codebase](#working-on-the-codebase)
17. [Plain-English glossary](#plain-english-glossary)

## What the product does

### Structured Customer requests

The Customer describes the need through a mandatory form. The form captures:

- a clear title and full description;
- the question that needs to be answered;
- the desired outcome;
- background and known context;
- relevant subject area, location and time period;
- urgency, required date and why the date matters;
- the activity, project or decision the work will support;
- preferred product format;
- success criteria;
- constraints and caveats;
- available supporting information; and
- sensitivity and handling instructions.

The Customer does not choose an internal route, organisation, recipient or
Analyst. Internal routing is the responsibility of authorised staff.

The page groups the request into four plain-language sections. A sticky progress
bar shows how many required fields remain in each section, completed sections
are marked clearly, focused narrative fields show their character allowance and
the error summary links directly to each invalid field. Every field remains
mandatory at both the React and FastAPI boundaries.

Incomplete work can be saved as a private draft. Submitting a complete request
creates an immutable submitted revision, a stable reference and one durable
Camunda process-start command. Browser retries cannot create duplicate requests.

### Clear tracking and actions

Every user has a role-appropriate Home page. Personal actions and organisation
workload are labelled separately. Notifications link to the exact request or
human task the user is authorised to open.

Customers see:

- current requests, completed requests and private drafts;
- plain-English progress and the current responsible organisation;
- requests for additional information;
- cancellation when the request is in an allowed state;
- the complete attributable activity history;
- released files or approved product links; and
- a one-time service-feedback form after completion.

Routing organisations see their queue while responsible and retain scoped
tracking afterwards. They can see where the request now sits, but they do not
approve the final product.

### Human-led organisational routing

The organisation hierarchy is data-driven. At each stage the current routing
user chooses one direct child of their own unit:

```text
CRIOC
  → selected command
    → selected Ops group
      → selected delivery team
```

Every configured sibling is a real staffed destination. There is no hidden SSG
fallback. A route cannot skip a level or cross into a sibling branch.

The initial operational route is:

```text
CRIOC → JOCK → ACSA-B Ops → SSG Team
```

The complete tree, visibility rules and all synthetic users are in
[Organisation and routing](docs/architecture/ORGANISATION_AND_ROUTING.md).

### Delivery-team work

A delivery-team Manager assigns:

- exactly one accountable Lead Analyst; and
- up to ten optional Contributing Analysts.

The assignment screen uses independent checkboxes for Contributors, shows a
selected count and excludes the chosen Lead. Analysts do not claim unassigned
delivery tickets. The Manager assigns them.

The Lead owns the Camunda production task. Contributors can collaborate on the
authorised request and team work, but cannot complete the Lead's parent task.

Team workspaces include:

- an actionable, unit-scoped work queue and workflow-derived Kanban board;
- workload, due-date, assignment and blocker information;
- people and effective-dated membership history;
- team-scoped colleague profiles with a direct return to the People register;
- a shared calendar and availability view;
- current team activity; and
- scoped team statistics.

The MVP navigation deliberately omits the advanced Planning and Handover
surfaces. Their existing server-side records are retained, but daily team work
is presented through one named workspace rather than several competing tools.

During active production, any current delivery-team Manager can send a recorded
task hastener to one assigned Analyst or to the Lead and all Contributors
assigned within that team. The reminder appears in each recipient's
notifications even if general assignment notifications are disabled, and an
exact-request link opens the board item regardless of filters or pagination. It
is visible in the Customer's accountable request history but is not a workflow
command: it does not change the owner, assignments or Camunda stage.

### Personal and team calendars

Every authenticated account has a personal calendar. Any user can add their own
leave, training, course or appointment.

When a user belongs to a workspace, personal events automatically appear in the
current team calendar. Details are visible by default. If the user selects
`Private appointment`, colleagues see only `Busy` and the time. Users without a
team retain a personal-only calendar.

Only delivery-team Managers can create request-linked commitments for named
Analysts. Ordinary personal events cannot be attached to a ticket.

### Product management and release

The Lead can build a product package containing:

- managed PDF, DOCX or PPTX files; and/or
- approved HTTPS product links.

Files enter private quarantine, are checked for size and type, and are scanned by
ClamAV. A failed or unavailable scan never releases a product. Clean files are
promoted to private storage and remain accessible only through an authorised
FastAPI download.

The Team Manager checks the submitted package. The QC Manager performs the final
review and dissemination. The Customer then receives the approved file or link
inside their dashboard.

### Related-request review

Authorised reviewers can compare the current submission with previous requests
they are permitted to see. Matching uses all submitted fields and combines
full-text, bounded field similarity and an optional local semantic projection.

The comparison is evidence for a human. It never changes the route, closes a
request or recommends a business decision. The reviewer records whether a result
is related, a possible duplicate, or not relevant.

### Administration

Platform Administrators can:

- create, edit, deactivate and reactivate accounts;
- review account requests and password-assistance notifications;
- maintain safe profile and organisation metadata;
- prepare organisation and workflow-configuration changes;
- approve another Administrator's proposed configuration;
- activate an approved effective-dated revision; and
- change the global visual classification marking.

Administration does not grant request or product content access. The application
checks that separation in FastAPI, not only in the interface.

## Who uses it

| Role | Purpose | Main actions |
|---|---|---|
| Customer | Ask for work and receive the result | Draft, submit, track, answer, cancel, download, give feedback |
| CRIOC Routing User | Understand and direct new demand | Claim, review, request information, close or choose a command |
| Request Coordination User | Coordinate work inside the selected command | Claim, hold, return, close or choose an Ops group |
| Ops Routing User | Direct work to a delivery team | Claim, return or choose a direct team |
| Team Manager | Make delivery accountable | Assign Lead and Contributors, oversee work, review product |
| Team Analyst | Produce the product | Work as Lead or Contributor, clarify, package and submit |
| QC Manager | Protect release quality | Review, return, approve and disseminate |
| Platform Administrator | Maintain safe platform metadata | Accounts, profiles, organisation, configuration and marking |

Workspace position is independent from workflow role. A routing organisation has
Managers and Members for roster and collaboration purposes, but both positions
perform the same claim-based routing decision. Delivery-team Managers have the
additional assignment, board, capacity and commitment controls needed for team
delivery.

The [current user stories](docs/USER_STORIES.md) provide detailed acceptance and
failure behaviour for every role.

## How a request moves through the service

### Part 1: route to a delivery team

![Request submission and organisational routing](docs/assets/architecture/03-routing-workflow.svg)

### Part 2: produce, review and release

![Product production, review and release workflow](docs/assets/architecture/04-delivery-workflow.svg)

The workflow contains deliberate loops:

- CRIOC may ask the Customer for missing information.
- A command may place the request on hold and later resume it.
- The Lead may ask the Customer a direct production question.
- The Team Manager or QC Manager may return the product to the same Lead.
- The Customer may withdraw or cancel an eligible active request.

After the delivery team is selected, the product does not travel back through
CRIOC, command or Ops for approval. It goes from Lead to Team Manager to QC Manager
to Customer.

The complete task and outcome table is in the
[Workflow and Camunda guide](docs/architecture/WORKFLOW_AND_BPMN.md).

## What users see

### Sign-in

![ISTARI sign-in](docs/assets/screenshots/login.png)

The sign-in page provides account access, account-request and forgotten-password
routes. A thin global classification bar appears above both public and protected
pages.

### Customer requests

![Customer request dashboard](docs/assets/screenshots/customer-request-dashboard.png)

The Customer dashboard separates action-needed, active and completed work. Titles
and references open the exact request. Released products appear inside the owning
request, not as public links.

### Team delivery

![Team workflow board](docs/assets/screenshots/team-workflow-board.png)

The team board is a visual collaboration view of authoritative request and
package state. Moving or editing a board item does not bypass the Camunda human
task or FastAPI workflow policy.

More current application views are catalogued in
[Browser and workflow evidence](docs/assurance/BROWSER_AND_WORKFLOW_EVIDENCE.md#current-application-screenshots).

## Architecture in plain English

The browser talks to one API. That API is the security boundary for application
data and actions.

![ISTARI Service container architecture](docs/assets/architecture/02-container-view.svg)

### Web application

The web interface is built with React 19, TypeScript, Vite, React Router,
TanStack Query, React Hook Form and Zod. It provides accessible pages, forms,
queues, calendars, boards, charts and administration workspaces.

Nginx serves the production build in the local container and forwards `/api/`
requests to FastAPI. React never connects directly to Camunda or PostgreSQL.

### Application API

FastAPI validates input, authenticates sessions, checks permissions, coordinates
business use cases and returns bounded response models. Route handlers translate
HTTP. Services and policy modules hold application rules. Repositories own
database access. Adapters isolate Camunda, product storage and malware scanning.

### Application database

PostgreSQL 17 is the authority for:

- users, profiles, passwords and sessions;
- requests, drafts and immutable submitted revisions;
- organisation and effective-dated configuration;
- route, assignment and participant history;
- clarification, notes and feedback;
- product metadata and release records;
- calendars, team planning and notifications;
- operational facts and dashboard projections; and
- tamper-evident audit events.

pgvector, PostgreSQL full-text search and trigram similarity support the bounded
related-request projection. Search always reapplies object and route permission.

### Camunda

Camunda 8.9 is the authority for BPMN process position and human-task lifecycle.
It receives bounded identifiers, candidate groups, assignee IDs and outcome
variables. It does not receive request narrative, product content, credentials,
session values or file bytes.

### Worker

A separately running Python worker dispatches durable process and task commands,
reconciles PostgreSQL projections with Camunda, enriches authorised search records
and reports a content-free heartbeat. Database leases and generations prevent a
stale worker from recording success after another worker takes over.

### Product storage and scanner

The local environment uses a private named volume. The API streams uploads into
quarantine and asks an internal ClamAV service to scan them. The storage volume is
not published by the web server. Downloads pass through FastAPI and repeat the
ownership and release checks.

### Why PostgreSQL and Camunda do not drift silently

![Durable workflow command and reconciliation](docs/assets/architecture/05-durable-workflow-command.svg)

PostgreSQL and Camunda cannot share one database transaction. ISTARI therefore:

1. authorises the person and exact action;
2. commits durable intent and audit context;
3. performs the Camunda call outside the SQL transaction;
4. proves the exact external result; and
5. commits the visible projection.

If a dependency is unavailable, the request shows pending or an explicit support
state. The system does not invent progress.

The detailed design, trust boundaries, failure behaviour and scaling model are
in [System architecture](docs/architecture/SYSTEM_ARCHITECTURE.md). The editable
C4 model is in
[`docs/architecture/structurizr/workspace.dsl`](docs/architecture/structurizr/workspace.dsl).

## Security and data protection

ISTARI applies security at the API and data boundaries.

### Access control

Every protected operation considers:

1. active authenticated identity;
2. representative role;
3. effective organisation and workspace membership;
4. request ownership, selected route or participant assignment;
5. current application and workflow state;
6. expected version; and
7. separation-of-duty rules.

List queries are scoped before records leave PostgreSQL. Detail and mutation
routes repeat the object check. Random identifiers are not treated as permission.

### Sessions and browser protection

- Passwords use Argon2 and are never stored or logged in plain text.
- Sessions are server-side records addressed by opaque secure cookies.
- Mutating browser requests require a matching CSRF token.
- Sensitive administrative actions require recent step-up authentication.
- Login attempts share a PostgreSQL-backed rate limit across API instances.
- Trusted hosts, restricted CORS, body limits and security headers are enforced.
- Logs use safe metadata and correlation identifiers, not request bodies.

### Audit

Workflow and administrative events record the actor, object, action, prior state,
next state, reason, time and correlation context. Each event carries the prior
event hash and its own canonical hash so integrity verification can detect
tampering.

### Files

- file size, extension and detected type are constrained;
- quarantined content is not downloadable;
- complete bytes are malware scanned;
- failed or stale scan definitions fail closed;
- clean promotion and package association are fenced operations;
- external links require HTTPS and an approved hostname; and
- every download rechecks the owning Customer and released package.

### Accessibility

The interface is designed towards WCAG 2.2 Level AA. Authenticated pages provide
a keyboard-visible skip link, named landmarks, semantic forms and native controls.
Layouts reflow without horizontal document scrolling at a 320 CSS-pixel viewport.
Primary controls retain practical target sizes, keyboard focus is visually clear,
and automated tests guard text, classification-banner and control-boundary
contrast in both themes. Board and calendar work does not require drag gestures.

These technical controls do not constitute formal conformance. Representative
keyboard, screen-reader, zoom, text-spacing, forced-colour and cognitive reviews
remain required before deployment acceptance. See the
[accessibility evidence](docs/assurance/ACCESSIBILITY_EVIDENCE.md).

### Public-repository boundary

Never commit:

- real requests or product files;
- production URLs, network diagrams or organisation names;
- passwords, tokens, certificates, private keys or `.env` files;
- screenshots containing personal or operational information; or
- real classification or handling examples.

See [SECURITY.md](SECURITY.md), the
[service workflow threat model](docs/threat-model/service-request-workflow.md)
and [security scan evidence](docs/assurance/SECURITY_SCAN_EVIDENCE.md).

## Repository structure

```text
Istari-Service/
├── apps/
│   ├── api/                  FastAPI application, worker, migrations and tests
│   └── web/                  React application, styles and browser tests
├── docs/
│   ├── architecture/         Current system, workflow and organisation design
│   ├── specs/                Behaviour and acceptance records
│   ├── adr/                  Durable architecture decisions
│   ├── threat-model/         Risks, controls and verification expectations
│   ├── deployment/           Local, cloud-sandbox and release guides
│   ├── operations/           Support, recovery and configuration procedures
│   ├── assurance/            Dated test, scan and rehearsal evidence
│   ├── reference/            Stable role and permission lookup
│   └── assets/               Synthetic screenshots and architecture diagrams
├── infra/                    Local PostgreSQL, Camunda and ClamAV images
├── scripts/                  Guarded startup, quality, release and recovery tools
├── workflow/                 Executable BPMN process
├── docker-compose.yml        Complete loopback-only local environment
├── .env.example              Configuration names and synthetic local defaults
└── README.md                 Product and engineering entry point
```

### Code boundaries

Backend route handlers stay thin. Business rules belong in services, domain
policy and use cases. Persistence belongs in repositories. Camunda, storage,
scanner and other dependencies sit behind explicit ports or adapters.

Frontend pages and components render interaction. Typed API clients own network
contracts. Shared role, capability and navigation logic belongs in dedicated
libraries rather than being copied into pages.

Hand-written source files must stay at or below 350 lines. Markdown documentation
is exempt because a coherent guide is more useful than several artificial
fragments.

## Run the complete application locally

The supported local path uses Docker Compose and loopback-only host ports.

### Prerequisites

- Git
- Docker Desktop or another Docker Engine with Compose v2
- PowerShell 7.4 or later
- [uv](https://docs.astral.sh/uv/) when using the `-SeedDemoData` option
- at least 8 GB free memory for the complete stack
- enough disk space for container images, PostgreSQL, Camunda and scanner data

Windows, macOS and Linux details are in the
[local Docker guide](docs/deployment/LOCAL_DOCKER.md).

### 1. Clone and enter the repository

```powershell
git clone https://github.com/ShabalalaWATP/Reon.git
Set-Location Reon
```

### 2. Create local configuration

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace every `CHANGE_ME` value with a unique local secret. Keep
the file untracked. The intentionally simple `DEMO_USER_PASSWORD=admin` is only
for the synthetic local environment.

### 3. Start through the guarded helper

```powershell
pwsh -File ./scripts/start-local.ps1
```

The helper:

- rejects unsafe or incomplete local settings;
- builds and starts the Compose services;
- applies application database migrations;
- deploys the BPMN process to Camunda;
- waits for dependency health;
- verifies application readiness; and
- records workflow availability from inside the API container.

To explore a populated system rather than an empty one, add `-SeedDemoData`:

```powershell
pwsh -File ./scripts/start-local.ps1 -SeedDemoData
```

This walks realistic synthetic requests through the genuine workflow as the
demo accounts, leaving every team with finished products, live work and
routing queue items, and spreads the audit history over previous weeks so the
statistics pages show meaningful charts. Expect ten to fifteen minutes, mostly
spent respecting the login rate limit; interrupting and rerunning is safe
because completed journeys are detected and skipped.

### 4. Check health

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

`/health` confirms that the API process is running. `/ready` confirms that required
dependencies and the worker heartbeat are ready for ordinary use. Health output
is deliberately content-free.

### 5. Open the application

Open [http://localhost:5173](http://localhost:5173).

Useful local endpoints:

| Endpoint | Purpose |
|---|---|
| `http://localhost:5173` | ISTARI web application |
| `http://127.0.0.1:8000/health` | API liveness |
| `http://127.0.0.1:8000/ready` | Dependency and worker readiness |
| `http://127.0.0.1:8080` | Loopback-only local Camunda endpoint |

### 6. Stop the environment

```powershell
docker compose down
```

This stops containers but keeps named volumes. Follow the reset procedure in the
local Docker guide if you intentionally need a fresh synthetic database. Do not
delete volumes casually when they contain useful test evidence.

## Run from source

Source development keeps PostgreSQL, Camunda and scanning in Compose while the
API or web application runs on the host.

### Required host tools

- Python 3.12 or later
- `uv`
- Node.js 22 or later
- Corepack and pnpm 10

### Install dependencies

```powershell
corepack enable
pnpm install
uv sync --project apps/api --all-groups
```

### Start dependencies

Use the commands in
[Local source development](docs/deployment/LOCAL_SOURCE_DEVELOPMENT.md) to start
the exact dependency profile and apply migrations.

### Start FastAPI

```powershell
uv run --directory apps/api uvicorn istari_service.main:app --reload
```

### Start React

```powershell
pnpm --filter @istari-service/web dev
```

The Vite development server opens on its configured local port and forwards API
traffic according to the development configuration.

## Synthetic accounts

The local seed contains 100 synthetic Scottish-football display names:

- usernames: `admin1` through `admin100`;
- local-only password: `admin`;
- `admin1`: Platform Administrator;
- `admin2`: Customer John McGinn;
- `admin4` and `admin74`: representative CRIOC access;
- `admin5` and `admin76`: representative JOCK access;
- `admin6` and `admin82`: representative ACSA-B Ops access;
- `admin8`: SSG Team Manager Grant Hanley;
- `admin11`: SSG Team Analyst Lewis Ferguson;
- `admin15`: QC reviewer Angus Gunn;
- `admin100`: independent release Manager Neil Alexander; and
- `admin16`: intentionally inactive for access-control testing.

The complete account ID, name, role, organisation, workspace position and active
state for every user is maintained in the
[complete synthetic user directory](docs/architecture/ORGANISATION_AND_ROUTING.md#complete-synthetic-user-directory).

The password is read from `DEMO_USER_PASSWORD`, hashed at rest and never returned
by the API. Synthetic account seeding is refused unless the environment explicitly
allows local demo data.

## Configuration

`.env.example` is the safe variable-name and local-default reference. `.env` is a
local secret file and must never be committed.

Important configuration groups include:

- application environment and mock-data permission;
- application, migration, backup and Camunda database identities;
- Camunda address, authentication mode and process identifier;
- session, CSRF, trusted-host and CORS settings;
- database pool and worker lease sizing;
- file size, package size, storage path and scanner requirements;
- allowed external-product hostnames;
- search model revision and checksum;
- classification marking; and
- bounded feature flags for operational workspaces and configuration.

The authoritative explanation, allowed values, local examples and production
invariants are in the
[configuration reference](docs/deployment/CONFIGURATION_REFERENCE.md).

## Testing and quality gates

### Repository checks

```powershell
pnpm check
```

This runs repository policy tests, dead-code checks, source line limits,
terminology rules, documentation link and duplication checks, operational script
contracts, licence checks, OpenAPI compatibility, TypeScript and ESLint.

### Backend tests

```powershell
uv run --directory apps/api pytest
```

Pytest covers business policy, API contracts, workflow transitions,
authorisation, persistence, migrations, recovery, product handling and security
behaviour. Backend line and branch coverage must each remain at least 95 per cent.

### Frontend tests

```powershell
pnpm --filter @istari-service/web test
```

Vitest and React Testing Library cover role journeys, forms, accessibility,
loading, empty, denied, conflict, success and failure states. Frontend line and
branch coverage must each remain at least 95 per cent.

### Additional security and release checks

CI also includes dependency review and update automation, secret scanning,
CodeQL, package audits, Bandit, image scanning, workflow lint and container
security checks. The
[release runbook](docs/deployment/RELEASE_RUNBOOK.md) lists the complete
qualification sequence and evidence requirements.

Do not lower a threshold or suppress a finding only to make a candidate pass.

## Deployment choices

| Path | Appropriate use | Current status |
|---|---|---|
| Docker Compose on a developer workstation | Development and synthetic evaluation | Implemented and exercised |
| Compose on a protected AWS VM | Time-bounded private synthetic evaluation | Step-by-step guide available |
| Compose on a protected GCP VM | Time-bounded private synthetic evaluation | Step-by-step guide available |
| Compose on a protected Azure VM | Time-bounded private synthetic evaluation | Step-by-step guide available |
| Kubernetes with managed dependencies | Intended connected staging/production direction | Design only, not implemented or validated |

Cloud VM guides reuse the loopback-only Compose topology behind a protected
management tunnel. They are not production architectures and must contain only
synthetic data.

- [Deployment guide home](docs/deployment/README.md)
- [AWS synthetic sandbox](docs/deployment/AWS_SANDBOX.md)
- [GCP synthetic sandbox](docs/deployment/GCP_SANDBOX.md)
- [Azure synthetic sandbox](docs/deployment/AZURE_SANDBOX.md)
- [Kubernetes target design](docs/deployment/KUBERNETES_TARGET.md)
- [Production gates](docs/deployment/PRODUCTION_GATES.md)

## Documentation map

Start at the [documentation home](docs/README.md). The main current-state guides
are:

| Question | Document |
|---|---|
| What does the product do? | This README and [current user stories](docs/USER_STORIES.md) |
| How does the system fit together? | [System architecture](docs/architecture/SYSTEM_ARCHITECTURE.md) |
| How does Camunda move the request? | [Workflow and Camunda guide](docs/architecture/WORKFLOW_AND_BPMN.md) |
| Which organisations and users exist? | [Organisation and routing](docs/architecture/ORGANISATION_AND_ROUTING.md) |
| What can each role do? | [Role and permission matrix](docs/reference/ROLE_PERMISSION_MATRIX.md) |
| How do I run it locally? | [Local Docker](docs/deployment/LOCAL_DOCKER.md) |
| How do I configure it? | [Configuration reference](docs/deployment/CONFIGURATION_REFERENCE.md) |
| How do I operate or recover it? | [Operations guides](docs/operations/) |
| What security risks are controlled? | [Threat models](docs/threat-model/) and [SECURITY.md](SECURITY.md) |
| What has actually been tested? | [Assurance evidence](docs/assurance/) |
| What remains before production? | [Enterprise readiness gaps](docs/ENTERPRISE_READINESS_GAP_REGISTER.md) |
| What work is complete or open? | [Master implementation plan](docs/MASTER_IMPLEMENTATION_PLAN.md) |
| How did the codebase develop? | [Development story](docs/DEVELOPMENT_STORY.md) |

Specifications, ADRs and assurance records remain separate because they have
different purposes:

- a **specification** records detailed behaviour and acceptance criteria;
- an **ADR** records a decision and the reasons it is expensive to reverse;
- an **assurance record** preserves dated evidence; and
- a **current-state guide** explains how the product works now.

Current-state guides do not require readers to understand an earlier interface or
abandoned label. Historical context stays in the development story, ADRs and dated
evidence.

## Known production boundaries

The repository intentionally stops short of claiming production readiness.

The following are not implemented or approved here:

- production identity-provider federation and first-user bootstrap;
- a production joiner, mover, leaver and privileged-access process;
- production Camunda authentication beyond supported `BASIC` client mode;
- a validated highly available Camunda topology;
- an S3, GCS or approved enterprise product-storage adapter;
- production key management, retention approval and content-disarm service;
- infrastructure as code and an application Kubernetes chart;
- managed TLS, DNS, WAF, ingress and private-network deployment;
- accepted production SLIs, SLOs, capacity plan and alert ownership;
- approved backup, continuity and disaster-recovery targets;
- classification, privacy, residency and DPIA decisions for real data;
- named production service owners, support hours and training ownership; and
- connected-environment penetration testing and operational acceptance.

Working local software and strong automated coverage do not close those gaps.
Use the [production gates](docs/deployment/PRODUCTION_GATES.md) before deciding
whether any environment may hold real data.

## Working on the codebase

### Engineering principles

- Prefer simple, readable code over clever abstractions.
- Keep business rules out of HTTP handlers and React presentation components.
- Add an interface only where it protects a real external or persistence boundary.
- Recheck authorisation at the object and action boundary.
- Preserve explicit side effects and durable transaction ownership.
- Add regression tests for bug fixes and permission changes.
- Keep source files within 350 lines; documentation is exempt.
- Use UK English in user-facing text, documentation and comments.
- Keep examples synthetic and public-repository safe.

### Change records

- A user-visible feature starts with or updates an applicable file in `docs/specs/`.
- A material architecture choice adds or updates an ADR.
- A security-sensitive change updates the applicable threat model.
- A meaningful milestone updates the master plan and development story.
- Dated scan or rehearsal output belongs in assurance, not in a current guide.

### Before review

At minimum, run the checks closest to the change. Before presenting a coherent
release candidate, run the full repository, backend and frontend gates shown
above. Report exactly what ran and do not claim a scan, build, commit or push that
did not complete.

## Plain-English glossary

| Term | Meaning |
|---|---|
| BPMN | A standard diagram and execution format for events, human tasks, choices and paths. |
| Camunda | The workflow engine that remembers the current BPMN position and human task. |
| Candidate group | The organisation whose eligible users can take a shared routing task. |
| Claim | The act of one routing user taking personal responsibility for a shared task. |
| Lead Analyst | The person accountable for producing and submitting the product. |
| Contributor | A supporting Analyst with request access who cannot complete the Lead task. |
| Projection | A database view prepared for a dashboard or queue from authoritative events. |
| Reconciliation | Checking Camunda and PostgreSQL and safely resolving a delayed or interrupted update. |
| Durable command | A recorded instruction that can be retried and proved without losing the user's intent. |
| Outbox | PostgreSQL records of work that the worker must send to an external dependency. |
| Fenced worker | A worker that proves current lease ownership before recording success. |
| Effective-dated | A record whose start and end times determine when it applies. |
| Pinned configuration | The organisation and workflow revision retained by a request for its lifetime. |
| Managed product | A controlled file or approved link with package, review and release history. |
| Quarantine | Private storage used before a file passes validation and malware scanning. |
| Step-up authentication | Re-entering credentials so a sensitive administrative action uses fresh proof. |
| Object-level authorisation | Checking access to the exact request, task, team or product, not only the page. |

For deeper detail, continue with the [documentation home](docs/README.md).
