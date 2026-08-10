# ISTARI Service

ISTARI Service is a synthetic, human-led service-request application. It keeps
the visual language of ISTARI while replacing conversational intake with a
structured form and a transparent request dashboard.

The accepted MVP and the newer Product Evolution release candidate are kept
distinct. Product Evolution adds a guided configuration workspace, managed
products, personal work, notifications, enhanced planning and scoped analytics.
It remains non-production until the named acceptance gates are signed.

## Implemented vertical slice

- ISTARI-style login with representative service-delivery copy.
- Mandatory request form with save-and-resume drafts and duplicate-submit safety.
- Customer tracking, request detail, current owner, activity and stage journey.
- Stored Analyst-to-Customer clarification loops that return to the same Analyst.
- Role-filtered dashboards and queues for all seven representative user types.
- Hierarchy-aware operational statistics and role-specific landing views. Each
  grant exposes its root and descendants, never its parents or sibling branches.
- Shared team roster, calendar, Kanban board, planning and activity workspaces.
- Camunda 8.9 human-task routing with no automated business decisions.
- Managed PDF, DOCX and PPTX product review, QC, authenticated dashboard
  download, approved HTTPS product links and one-time mandatory Customer
  feedback. Historical plain-text products remain available for their owners.
- Guided organisation configuration using **Current configuration** and
  **Proposed changes**, searchable hierarchy context, independent approval,
  effective scheduling and immutable request pinning.

The routing model is JIOC → selected command → selected Ops group → selected
team. Every configured child is a real selectable Camunda destination. OSG Team
is the initial operational team, while every sibling team has synthetic Manager
and Analyst staffing so its own Camunda route can be exercised without borrowing
OSG users. Once an Analyst submits the product, it moves to the Team Manager and
QC Manager, then to an authenticated Customer download. It does not travel back
up the routing chain for approval.

The local MVP includes bounded identity administration for account provisioning,
profile editing, reversible account deactivation and organisation display-name
maintenance. Platform Administrators cannot inspect service-request content.
It also includes automatic, explainable related-request matching with recorded
human decisions, operational notes,
effective-dated team membership, calendar-backed capacity and workload-aware
reassignment. See the [implementation plan](docs/MASTER_IMPLEMENTATION_PLAN.md)
for implementation and assurance status.

## Architecture and documentation

React talks only to FastAPI. PostgreSQL 17.10 with pgvector stores product data
and the authorised request-search projection. Camunda 8.9.14
owns BPMN process position and user tasks. A separately deployable, fenced
worker drains the outbox, generates offline local request embeddings and
reconciles projections without coupling maintenance pressure to API replica
count. External Camunda, storage and scanner calls do not retain database lock
transactions.

The code is arranged as domain policy, application use cases, small ports and
infrastructure adapters. FastAPI routes and React components remain delivery
mechanisms, and object-level policy is enforced in the backend. Start with the
[documentation map](docs/README.md), [system architecture](docs/architecture/SYSTEM_ARCHITECTURE.md)
and [secure-by-design foundations](docs/architecture/FOUNDATIONS.md).

The local Camunda stack is for development only. Production OIDC/bootstrap and
an approved product-storage runtime are not implemented. Camunda authentication
supports only `NONE` and `BASIC`, with `NONE` forced for loopback-only local
Compose. There is no application Kubernetes chart, infrastructure as code or
validated production topology. The unimplemented direction and hard gates are
documented in the [Kubernetes target](docs/deployment/KUBERNETES_TARGET.md) and
[production gates](docs/deployment/PRODUCTION_GATES.md).

The current local runtime also applies a shared PostgreSQL login budget before
password hashing, bounds concurrent Argon2 work, runs the web and data-service
containers without root privileges, verifies loaded ClamAV definition freshness
and scans every deployed image in CI. See the [security policy](SECURITY.md) and
[August security specification](docs/specs/security-remediation-2026-08.md).

## Local setup

1. Install Docker Compose v2, Git and PowerShell 7.4 or later.
2. Copy `.env.example` to `.env` and replace every `CHANGE_ME` value. Leave the
   deliberately weak `DEMO_USER_PASSWORD=admin` only for this local synthetic MVP.
3. Run `pwsh -File ./scripts/start-local.ps1`.
4. Confirm `http://127.0.0.1:8000/ready` reports ready.
5. Open `http://localhost:5173`.

The guarded helper validates local-only settings, starts and waits for Compose,
deploys the BPMN, and records workflow availability from inside the API
container using `-AttestWithCompose`. Compose forwards database-pool, session and
process-identity variables. Complete Windows, macOS and Linux steps are in the
[local Docker guide](docs/deployment/LOCAL_DOCKER.md). Source-development and
private synthetic AWS/GCP/Azure sandbox paths are in the
[deployment index](docs/deployment/README.md).

The seeded logons are `admin1` through `admin99`, all using password `admin` in
local/test only. `admin1` is the Platform Administrator. `admin16` is
intentionally inactive, so its otherwise matching fixture password cannot start
a session. Every mock username, identity, role and assignment is documented in
[Organisation and routing](docs/architecture/ORGANISATION_AND_ROUTING.md);
[Mock users](docs/reference/MOCK_USERS.md) is the stable short-form locator. The shared password is
read only from `DEMO_USER_PASSWORD`, is hashed at rest, is never returned by the
API and mock seeding is refused outside the local environment.

Product Evolution capabilities are disabled by default in application and
Compose settings. The supplied `.env.example` enables them for the synthetic
local demonstration only. Keep `ACTION_WORKSPACE_ENABLED`,
`NOTIFICATIONS_ENABLED`, `MANAGED_PRODUCTS_ENABLED`,
`CONFIGURATION_ADMIN_ENABLED`, `PLANNING_EVOLUTION_ENABLED` and
`STATISTICS_EVOLUTION_ENABLED` false until their applicable acceptance gates
are complete in the intended environment.

## Checks

```powershell
pnpm check
uv run --directory apps/api pytest
pnpm --filter @istari-service/web test
```

Backend and frontend test runs enforce line and branch coverage as separate
95 per cent gates.

See the [configuration reference](docs/deployment/CONFIGURATION_REFERENCE.md),
[release runbook](docs/deployment/RELEASE_RUNBOOK.md) and
[implementation plan](docs/MASTER_IMPLEMENTATION_PLAN.md) for environment,
qualification and remaining-work detail.

## Assurance and acceptance

The implementation is mapped to explicit completion criteria. The current
evidence and the remaining human decisions are recorded in:

- [Definition of Done matrix](docs/assurance/DEFINITION_OF_DONE_MATRIX.md)
- [Final completion audit](docs/assurance/FINAL_COMPLETION_AUDIT.md)
- [Browser, workflow and current screenshot evidence](docs/assurance/BROWSER_AND_WORKFLOW_EVIDENCE.md)
- [Source-control baseline](docs/assurance/SOURCE_CONTROL_BASELINE.md)
- [Pilot baseline decisions](docs/decisions/PILOT_BASELINE_DECISIONS.md)
- [Pilot acceptance record](docs/assurance/PILOT_ACCEPTANCE_RECORD.md)

Product Evolution evidence and the enterprise-readiness boundary are recorded
in:

- [Configuration-administration usability](docs/specs/configuration-administration-usability.md)
- [Product Evolution Definition of Done](docs/assurance/PRODUCT_EVOLUTION_DEFINITION_OF_DONE_MATRIX.md)
- [Configuration and routing evidence](docs/assurance/CONFIGURATION_AND_ROUTING_EVIDENCE.md)
- [Product Evolution acceptance](docs/assurance/PRODUCT_EVOLUTION_ACCEPTANCE_RECORD.md)
- [Enterprise documentation index](docs/ENTERPRISE_DOCUMENTATION_INDEX.md)
- [Enterprise readiness gap register](docs/ENTERPRISE_READINESS_GAP_REGISTER.md)
