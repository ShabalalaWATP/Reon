# ISTARI Service

ISTARI Service is a synthetic, human-led service-request MVP. It keeps
the visual language of ISTARI while replacing conversational intake with a
structured form and a transparent request dashboard.

## Implemented vertical slice

- ISTARI-style login with representative service-delivery copy.
- Mandatory request form with save-and-resume drafts and duplicate-submit safety.
- Customer tracking, request detail, current owner, activity and stage journey.
- Stored Analyst-to-Customer clarification loops that return to the same Analyst.
- Role-filtered dashboards and queues for all seven representative user types.
- Exactly scoped operational statistics for JIOC, command, Ops and team Managers.
- Shared team roster, calendar, Kanban board, planning and activity workspaces.
- Camunda 8.9 human-task routing with no automated business decisions.
- Plain-text service-product review, QC, authenticated download and one-time
  mandatory Customer feedback.

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
It also includes recorded manual related-work checks, operational notes,
effective-dated team membership, calendar-backed capacity and workload-aware
reassignment. See `docs/MASTER_IMPLEMENTATION_PLAN.md` for implementation and
assurance status.

## Architecture

React talks only to FastAPI. PostgreSQL 17 stores product data. Camunda 8.9.14
owns BPMN process position and user tasks. An outbox and reconciliation boundary
keeps the product projection honest when the engine is unavailable or its search
index is briefly behind.

The code is arranged as domain policy, application use cases, small ports and
infrastructure adapters. FastAPI routes and React components remain delivery
mechanisms, and object-level policy is enforced in the backend. See
`docs/architecture/FOUNDATIONS.md` for the secure-by-design baseline.

The local Camunda stack is for development only. Production requires supported
infrastructure, OIDC, a compatible Helm chart and an appropriate Camunda licence.

## Local setup

1. Copy `.env.example` to `.env` and replace every `CHANGE_ME` value. Leave the
   deliberately weak `DEMO_USER_PASSWORD=admin` only for this local synthetic MVP.
2. Run `pnpm install`.
3. Run `uv sync --project apps/api --all-groups`.
4. Start the stack with `docker compose up --build`.
5. Open `http://localhost:5173`.

The seeded logons are `admin1` through `admin72`, all using password `admin` in
local/test only. `admin1` is the Platform Administrator. Mock identities and
roles are documented in `docs/reference/MOCK_USERS.md`. The shared password is
read only from `DEMO_USER_PASSWORD`, is hashed at rest, is never returned by the
API and mock seeding is refused outside the local environment.

## Checks

```powershell
pnpm check
uv run --directory apps/api pytest
pnpm --filter @istari-service/web test
```

See `docs/MASTER_IMPLEMENTATION_PLAN.md` for the final phased plan and remaining
production decisions.

## Assurance and acceptance

The implementation is mapped to explicit completion criteria. The current
evidence and the remaining human decisions are recorded in:

- `docs/assurance/DEFINITION_OF_DONE_MATRIX.md`;
- `docs/assurance/FINAL_COMPLETION_AUDIT.md`;
- `docs/assurance/BROWSER_AND_WORKFLOW_EVIDENCE.md`;
- `docs/decisions/PILOT_BASELINE_DECISIONS.md`;
- `docs/assurance/PILOT_ACCEPTANCE_RECORD.md`.
