# Maintainability and portable evaluation specification

Status: current engineering and evaluation contract, production acceptance excluded
Last reviewed: 18 August 2026

## Objective

Reduce avoidable code and query cost, make dead-code drift detectable, remove
stale documentation claims and provide one accurate architecture and setup path
for local, AWS, Google Cloud, Azure and future Kubernetes environments.

## Requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| MPE-01 | Remove only code proved unreferenced or test-only, preserving historical migrations and accountable evidence | Vulture, Knip, tests and reviewed diff |
| MPE-02 | Detect unused frontend files, exports and dependencies, including exports used only by tests | Normal and production-only Knip gates |
| MPE-03 | Detect high-confidence unused backend symbols on every repository check | Vulture gate |
| MPE-04 | Avoid one request-policy query per tracked request and bound broad visibility lists | Query-count and batching tests |
| MPE-05 | Avoid eager hidden dashboard product lookups and repeated date/calendar work | Frontend behaviour tests and build |
| MPE-06 | Required team-board data must fail and retry as one coherent state | All-dependency outage/recovery test |
| MPE-07 | Local startup must deploy and attest BPMN from a network context that can resolve Compose services | Behavioural PowerShell contract and smoke |
| MPE-08 | Environment variables documented for Compose must actually reach the API container | Compose/configuration review and contract docs |
| MPE-09 | Production PostgreSQL configuration must require server-identity verification using an asyncpg-compatible URL | Settings rejection and dialect connect-argument test |
| MPE-10 | Readiness must always validate the active sealed runtime configuration, independently of whether its administration surface is enabled | API readiness tests |
| MPE-11 | Architecture, trust boundaries, data authorities, failure modes, scaling and recovery must have one current authority | System architecture and documentation home |
| MPE-12 | Setup guides must distinguish executable synthetic evaluation from unimplemented production targets | Deployment matrix, local and cloud guides, production gates |
| MPE-13 | Documentation must reject broken relative links, repeated long-form prose and a duplicated full user roster | Automated documentation gates |
| MPE-14 | Historical ADR, threat, assurance and development records remain traceable but must not claim to describe the current candidate | Historical banners and current-authority links |
| MPE-15 | Load role and workspace pages on demand and detect entry-bundle growth | Vite manifest, production build and enforced entry budgets |
| MPE-16 | Avoid shell reads and polling that the current role or active page cannot use | Role and notification workspace tests |
| MPE-17 | Project and mutate notification recipient batches with bounded reads rather than one eligibility, preference and recipient query per target | Projection and state behaviour tests |
| MPE-18 | Restore an unchanged configuration without incrementing stable unit versions or rewriting an identical organisation closure | Restart and materialisation idempotency tests |
| MPE-19 | Keep selected routing and calendar edit state aligned with the item visibly presented, and format browser date values in local calendar time | Focused state and date regression tests |
| MPE-20 | Remove production abstractions proved to exist only for their own tests, and keep test adapters outside the production package | Reference review, Vulture and full tests |
| MPE-21 | Keep HTTP application assembly separate from lifespan and persistence initialisation, with stable middleware, router and error-handler composition | Architecture tests, focused application tests and reviewed dependency direction |
| MPE-22 | Persist each notification-projection failure, retry it with bounded backoff and report a content-free batch failure without rolling back other outcomes | Projection reconciliation and worker-accounting tests |
| MPE-23 | Expose bounded analytics rebuild and replay entry points and reject analytics definition drift unless its version advances | Maintenance-entrypoint, definition-integrity and replay tests |
| MPE-24 | Consolidate duplicated frontend activity pagination, upcoming-calendar presentation, payload schemas and test fixtures without changing product behaviour | Focused component tests, full frontend suite and dead-code gate |

## Non-functional constraints

- No real service information, private endpoint or credential may enter source or
  evidence.
- Local and VM sandboxes remain loopback-bound and synthetic-only.
- Cloud guides use private management tunnels and do not expose Camunda,
  PostgreSQL or the application directly to the internet.
- Production instructions remain blocked until identity, Camunda security,
  product storage/scanning, IaC, observability and joined recovery exist.
- Source files retain the 350-line limit; Markdown evidence is exempt.
- Backend and frontend retain independent 95 per cent line and branch gates.

## Deferred improvements

The following are valid next milestones, not hidden claims of this one:

- batch product-release metadata for expanded completed history;
- debounced/abortable board search;
- push board filtering, pagination and concurrent WIP enforcement into
  PostgreSQL;
- split and format the densest React orchestration modules before enforcing a
  practical source-line-length gate.

The earlier keyset-pagination, independently deployed worker, membership
projection, external-I/O fencing, streamed-download transaction and focused
product-port items are implemented. They are no longer deferred work.
