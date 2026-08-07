# Product Foundations

## Purpose

These foundations define what must remain true as the initial vertical slice
grows into the complete pilot MVP. A feature is not complete when only its happy
path works.

## Dependency direction

```text
React features -> typed API client -> FastAPI delivery layer
                                      |
                                      v
                              application use cases
                                      |
                                      v
                              domain rules and policy
                                      ^
                                      |
                    ports <- PostgreSQL and Camunda adapters
```

The domain does not know about HTTP, SQLAlchemy, Camunda or React. Use cases own
transactions and coordinate narrow ports. Adapters translate external contracts.

## Interface design thesis

- **Visual thesis:** a calm, dark ISTARI operational workspace with crisp type,
  restrained cyan accents and a clear hierarchy, using panels only where they
  provide interaction or essential context.
- **Content plan:** the login establishes the product and authorised-access
  boundary; the application opens directly on the user's queue, request list or
  tracking workspace; organisation and request detail supply context without a
  marketing-style dashboard.
- **Interaction thesis:** use one restrained login entrance, subtle status and
  route transitions, and clear hover or focus feedback. All motion respects
  reduced-motion preferences and never delays an operational action.

## Authoritative records

| Concern | Authority |
| --- | --- |
| Process position and user-task lifecycle | Camunda |
| Identity, session, request revisions and assignments | Product PostgreSQL |
| Stable dashboard projection | Product PostgreSQL, reconciled with Camunda |
| Human actor and reason | Product audit event |
| Service product, dissemination and feedback | Product PostgreSQL |

PostgreSQL and Camunda are not one transaction. A committed outbox command,
stable request business ID, idempotent dispatch and reconciliation are mandatory.
An engine outage must create a visible pending or error state, never an invented
route. Claims and completions use two product transactions around the external
effect, with final-boundary reauthorisation, recoverable leases and engine-state
proof as defined in [ADR 0003](../adr/0003-durable-human-workflow-commands.md).

## Authorisation model

Every protected operation evaluates:

1. active authenticated identity;
2. permitted role and action;
3. operational scope;
4. request ownership or task assignment;
5. current domain and workflow state;
6. separation-of-duty constraints.

List queries are scoped before records leave the database. Detail and mutation
paths recheck the object. Random identifiers reduce enumeration but do not replace
policy. The supporting Platform Administrator manages safe identity, role and
configuration metadata only, unless a separate audited support-access process is
approved later.

## Data integrity and audit

- Drafts are mutable only by their Customer and are not started in Camunda.
- Submission creates an immutable revision and one start command atomically.
- Later clarification and notes append history rather than rewriting it.
- Each workflow event records actor, time, action, reason, prior state, next state,
  object, task and correlation identifiers.
- Each event carries the prior event hash and its own canonical event hash.
- State changes use expected versions to reject duplicate or stale actions.
- Pending workflow commands are not actionable. Retry exhaustion becomes an
  explicit support-owned state and never silently reopens work.
- Database constraints enforce one active session token hash, valid role values,
  ownership links and one feedback record per completed request.

## Operational baseline

- Separate least-privileged application and Camunda databases and credentials.
- Typed settings, no checked-in secrets and no mock authentication outside local
  mode.
- Liveness reports process health only. Readiness reports dependency categories
  without content or credentials.
- Structured logs use correlation identifiers and safe metadata, never request
  bodies, service products, cookies or tokens.
- Migrations are reviewed, reversible where practical and tested from an empty
  database and the previous release.
- Backups, restore evidence, retention and deletion behaviour are pilot gates.
- Ordinary pages and API operations target p95 below two seconds at agreed pilot
  load. Workflow completion may acknowledge a clearly visible pending projection.
- The async PostgreSQL pool is configured per API instance. The local pilot uses
  20 retained and 30 overflow connections for its 50-user rehearsal; deployment
  sizing must keep the sum across replicas inside the database connection budget.

## Quality baseline

- Backend and frontend application code each maintain 95 per cent line and branch
  coverage, with stronger scenario expectations on policy and transitions.
- Hand-written source files stay within 350 lines.
- Static typing, formatting, lint, build, dependency, secret and container checks
  run in CI.
- WCAG 2.2 AA is tested for representative keyboard, focus, error and reduced-
  motion journeys.
- Contract tests protect repository and workflow substitutions.
- Pilot security testing includes cross-role, cross-scope, direct-identifier,
  invalid-transition, session, CSRF, audit and logging cases.

## Change rule

Add a dependency only when it materially improves correctness, security or
maintainability. A material architecture change needs an ADR. A security-sensitive
feature updates the threat model before it is considered complete.
