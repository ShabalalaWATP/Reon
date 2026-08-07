# ADR 0001: Application and Workflow Boundaries

## Status

Accepted, 6 August 2026.

## Context

The product needs a custom React experience, a FastAPI security boundary and an
executable human workflow. PostgreSQL and Camunda cannot participate in one ACID
transaction, and browser access to Camunda would bypass product authorisation and
couple the UI to engine contracts.

## Decision

- Use a pnpm workspace with React/Vite and a Python 3.12+ FastAPI service.
- Use PostgreSQL 17 for product data and a separate PostgreSQL database for
  Camunda secondary storage. Camunda primary execution data remains engine-owned.
- Pin local development to the unified `camunda/camunda:8.9.14` image.
- Integrate through the V2 Orchestration Cluster REST contract, using the official
  `camunda-orchestration-sdk` 9.0.1 async client behind a `WorkflowEngine` port.
- Camunda owns process position and user-task lifecycle. Product PostgreSQL owns
  users, sessions, submitted content, assignments, service products,
  feedback, append-only audit and the stable Customer-facing status projection.
- FastAPI is the only browser-facing gateway and rechecks role, assignment,
  Customer ownership, expected status and CSRF on every mutation.
- Start and completion commands use a transactional outbox. The request UUID is
  the Camunda business ID, with engine-side business-ID uniqueness enabled.
  Dispatch and reconciliation are idempotent and tolerate eventually consistent
  task search.
- Store only opaque identifiers and routing choices in workflow variables. Never
  read or write Camunda-owned database tables.
- Local mock users authenticate to FastAPI. A narrowly scoped backend client calls
  Camunda, so application audit is authoritative for the human actor in the MVP.
- Drafts exist only in product PostgreSQL. Submitting a draft atomically creates an
  immutable revision and the workflow-start outbox command.
- Notes, manual related-record links, workload projections and safe administrator
  metadata remain product concerns. They must not be stored in workflow variables.

## Consequences

The product remains usable with a purpose-built UI and stable domain language.
Camunda can be upgraded or replaced behind one port, but workflow reconciliation
is mandatory. Production requires OIDC, supported infrastructure, a compatible
Helm release and an appropriate Camunda Self-Managed Enterprise licence.
