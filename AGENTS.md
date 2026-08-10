# ISTARI Service Repository Instructions

These instructions supplement Alex Orr's global Codex instructions.

## Product boundary

- This is a synthetic, public-repository-safe service-request MVP.
- Use the agreed representative language: Customer, CRIOC Routing User, Request
  Coordination User, Ops Routing User, Team Manager, Team Analyst, QC Manager,
  service product and dissemination. Keep technical enum values stable
  where changing them would add migration risk.
- Do not introduce legacy RFI, RFA, CM, military, collection-management,
  chatbot or agent-routing language into application code, schemas, routes,
  BPMN IDs, tests or user-facing copy.
- The executable workflow is human-led. Camunda may route named human decisions,
  but it must not choose category, priority, delivery team, specialist, approval
  or release recipients.
- Keep all examples fictional. Scottish footballer names are synthetic mock
  identities and make no claim about the real people. Seeded organisational
  siblings are first-class selectable routes, not disabled demonstration data.

## Stack and quality gates

- Backend: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic.
- Frontend: React, Vite, TypeScript, React Router, TanStack Query, React Hook Form,
  Zod, Vitest and React Testing Library.
- Workflow: Camunda 8.9 through the V2 Orchestration Cluster API.
- Persistence: PostgreSQL 17 for application data and a separate Camunda
  secondary-storage database. Tests may use SQLite where PostgreSQL semantics are
  not under test.
- Maintain at least 95 per cent line and branch coverage independently for
  backend and frontend application code.
- Keep hand-written source files at or below 350 lines. Markdown documentation is
  exempt and may exceed 400 lines when required for traceability; organise long
  documents with clear headings instead of splitting one authority into copies.
- Every feature begins with a spec. Material decisions require an ADR, and
  security-sensitive work requires a threat-model update.
- Meet WCAG 2.2 AA for pilot journeys and target a p95 below two seconds for
  ordinary pages and API calls at agreed pilot load.

## Architecture boundaries

- Camunda is authoritative for workflow position and user-task lifecycle.
- PostgreSQL is authoritative for users, sessions, form content, assignments,
  deliverables, feedback, audit history and the requester-facing read model.
- React calls FastAPI only. It must never call Camunda directly.
- FastAPI must enforce role, assignment and object-level authorisation even when
  Camunda candidate groups are configured.
- Use a transactional outbox and idempotent reconciliation between PostgreSQL
  and Camunda. Never access Camunda-owned tables from application code.
- Keep route handlers thin and side effects explicit.
- Keep domain rules free of FastAPI, SQLAlchemy, Camunda and React imports.
- Application use cases depend on small repository, workflow, audit, clock and
  identity ports. Infrastructure adapters implement those ports.
- Centralise role, scope, ownership and action policy. Navigation hiding is never
  an authorisation control.
- Keep React feature components focused on rendering and interaction. Put API
  access, route policy and server-state orchestration in dedicated modules.
- Apply SOLID principles to protect real boundaries, not to manufacture layers,
  registries or dependency containers with no current use.
- The supporting Platform Administrator may manage identities, roles and safe
  configuration metadata but has no implicit access to request content.
- Audit workflow-changing actions with actor, object, prior state, next state,
  reason and correlation identifiers. Make the event chain tamper-evident.

## Common commands

- Install: `pnpm install` and `uv sync --project apps/api --all-groups`
- All static checks: `pnpm check`
- Backend tests: `uv run --directory apps/api pytest`
- Frontend tests: `pnpm --filter @istari-service/web test`
- Local stack: `docker compose up --build`
