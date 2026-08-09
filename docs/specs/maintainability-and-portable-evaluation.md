# Maintainability and portable evaluation specification

Status: implemented local engineering milestone, production acceptance excluded
Last reviewed: 8 August 2026

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
| MPE-11 | Architecture, trust boundaries, data authorities, failure modes, scaling and recovery must have one current authority | System architecture and documentation index |
| MPE-12 | Setup guides must distinguish executable synthetic evaluation from unimplemented production targets | Deployment matrix, local and cloud guides, production gates |
| MPE-13 | Documentation must reject broken relative links, repeated long-form prose and a duplicated full user roster | Automated documentation gates |
| MPE-14 | Historical ADR, threat, assurance and development records remain traceable but must not claim to describe the current candidate | Historical banners and current-authority links |
| MPE-15 | Load role and workspace pages on demand and prevent the original monolithic entry bundle returning unnoticed | Vite manifest, production build and enforced entry budgets |
| MPE-16 | Avoid shell reads and polling that the current role or active page cannot use | Role and notification workspace tests |
| MPE-17 | Project and mutate notification recipient batches with bounded reads rather than one eligibility, preference and recipient query per target | Projection and state behaviour tests |
| MPE-18 | Restore an unchanged configuration without incrementing stable unit versions or rewriting an identical organisation closure | Restart and materialisation idempotency tests |
| MPE-19 | Keep selected routing and calendar edit state aligned with the item visibly presented, and format browser date values in local calendar time | Focused state and date regression tests |
| MPE-20 | Remove production abstractions proved to exist only for their own tests, and keep test adapters outside the production package | Reference review, Vulture and full tests |

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

- keyset pagination and matching PostgreSQL indexes for unbounded registers;
- batch product-release metadata for expanded completed history;
- debounced/abortable board search;
- move effective-dated membership reconciliation out of every HTTP request while
  ensuring stale projections cannot over-authorise access;
- lease workflow commands and managed-product operations before Camunda,
  storage or scanning I/O so database locks are not held across the network;
- close database sessions before streaming product downloads;
- push board filtering, pagination and concurrent WIP enforcement into
  PostgreSQL;
- split product repository capabilities and deploy the maintenance worker
  independently from API replicas;
- split and format the densest React orchestration modules before enforcing a
  practical source-line-length gate.

## Second simplification pass

The 8 August 2026 review applied only changes with a bounded behavioural proof:

- top-level routes and Board, Calendar and Planning workspace views now load on
  demand, reducing the common JavaScript entry from 457.15 kB to 214.89 kB;
- the build now reads the Vite manifest and fails above 325 kB initial
  JavaScript or 110 kB initial CSS. The measured static entry is 300,068 bytes
  JavaScript and 95,306 bytes CSS, including its static vendor imports;
- the shell no longer requests team workspaces for non-team roles and the
  Notifications page supplies its count while its own list is polling;
- notification recipient projection uses set-based user, membership,
  preference and existing-recipient reads, one recipient flush and one
  checkpoint refresh per selected batch. Notification state targets are locked
  by one bounded query;
- an unchanged active configuration no longer changes organisation-unit
  versions or deletes and reinserts an identical closure;
- selected destinations remain visibly selected when a filter does not match,
  calendar occurrence editors remount for a different occurrence, and browser
  date defaults use local calendar components;
- a speculative planning-event port and unused repository methods were removed,
  while the in-memory product storage fake moved under test support.

The review also confirmed larger transaction and scaling changes that should
not be disguised as safe cleanup. They remain explicit milestones above with
concurrency, recovery and PostgreSQL evidence required before implementation.

The strict Ruff cyclomatic scan now reports eight functions above a complexity
of 10, down from nine before this pass. Each remaining site was reviewed. They
are explicit environment-security checks, application composition,
configuration preview rules, hostile-document inspection, workflow invariants
or state-transition semantics. Extracting branches solely to satisfy the score
would spread the same decisions across more files. Configuration preview and
application composition remain candidates for responsibility-based extraction
when their next functional change provides a behavioural boundary.
