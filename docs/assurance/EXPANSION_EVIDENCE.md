# Expansion Evidence Ledger

This ledger records reproducible evidence for completed expansion phases. It is
not a production approval. Security scans, browser coverage, performance,
backup/restore and stakeholder sign-off remain programme-level gates.

## Expansion 0: Rebaseline and authority

| Evidence | Record |
| --- | --- |
| Specification | `docs/specs/service-operations-expansion.md` |
| Decisions | ADRs 0006 to 0010, accepted locally |
| Threat models | Management and analytics, team workspaces and calendars, and service-request workflow models |
| Scoped statistics | Cross-branch API matrix, content-minimisation assertions, deterministic aggregate oracle, feedback cohort suppression, accessible chart/table parity and projection freshness states |
| Organisation | 40 units and 72 synthetic Scottish-player accounts, including a Manager and Analyst for every team |
| Remaining | Exact seeded management grants are delivered in Expansion 3 |

## Expansion 1: Customer data quality and closure

| Evidence | Record |
| --- | --- |
| Migration | `0003_customer_drafts.py`; empty upgrade, downgrade to `0002`, re-upgrade and Alembic drift check passed |
| Backend | Private draft ownership, stale-version, atomic submission, required-field, product-link and one-time feedback tests |
| Frontend | Draft, mandatory form, dashboard, released-product and feedback journeys with axe checks |
| Security | Customer object scope, authenticated no-store download, CSRF and duplicate-submit regression tests |
| Recovery | Retry-safe draft submission creates one request and one workflow-start command |

## Expansion 2: Analyst clarification

Recorded on 7 August 2026.

| Evidence | Record |
| --- | --- |
| Specification | `docs/specs/service-operations-expansion.md`, Analyst clarification section |
| Decision | `docs/adr/0010-versioned-analyst-clarification-loop.md` |
| Threat model | `docs/threat-model/service-request-workflow.md` |
| Migration | `0004_production_clarifications.py`; empty upgrade, drift check, downgrade to `0003`, re-upgrade and second drift check passed |
| Backend | `uv run --directory apps/api pytest -q`: 462 passed, 99.10% line and 96.22% branch coverage |
| Frontend | `pnpm --filter @istari-service/web test`: 158 passed, 99.30% line and 95.31% branch coverage |
| Workflow | BPMN validation: 11 user tasks, 10 gateways, 35 flows and complete diagram data; validator mutation suite and V2 mock contract passed |
| Live engine | Camunda 8.9.14 with PostgreSQL secondary storage completed two clarification loops on DIGOC → NCGI-A Ops → OSG Team, retained the same Analyst and released the product |
| Alternative route | The same engine completed SYGOC → Nimbus Ops → Beacon Team with Beacon-specific Manager and Analyst groups |
| Scope | Exact Customer, assigned Analyst and Team Manager content access; Platform Administrator denied; trackers receive metadata only |
| Static checks | Ruff format/check, mypy, TypeScript, ESLint, line-limit, terminology and production build passed |
| Remaining programme proof | Playwright browser matrix, accessibility manual review, security scans, performance and recovery rehearsal remain Expansion 8 gates |

## Git state

The repository remains local with no configured private remote or initial commit.
The master plan keeps sponsor confirmation and remote selection open rather than
claiming backup or review evidence that does not exist.

## Expansion 3: Management grants and analytics facts

Recorded on 7 August 2026.

| Evidence | Record |
| --- | --- |
| Specification | `docs/specs/service-operations-expansion.md`, organisation scope and statistics sections |
| Decisions | ADR 0006 explicit grants and ADR 0007 content-free analytics |
| Threat model | `docs/threat-model/management-and-analytics.md` |
| Migration | `0005_management_analytics_foundations.py`; empty upgrade, drift check, downgrade to `0004`, re-upgrade and second drift check passed |
| Seed | 42 deterministic grants: named JIOC, command and Ops statistics scopes plus exact-team grants for every active Team Manager |
| Scope | Exact, descendant, ancestor, sibling, wrong-action, inactive, expired and revoked cases passed; stale mutation versions denied |
| Hierarchy | 40 self rows plus bounded ancestor paths; cycle and missing-parent rebuilds rejected |
| Projection | Authoritative event append refreshes idempotent request facts and stage intervals; full rebuild produces a ready checkpoint |
| Minimisation | Analytics schemas exclude title, description, Customer ID, product text, clarification text, reasons and feedback comments |
| Backend | `uv run --directory apps/api pytest -q`: 471 passed, 99.18% line and 96.54% branch coverage |
| Static and schema | Ruff, mypy and line-limit passed; PostgreSQL and SQLite metadata compilation passed |

## Expansion 4: Scoped operational statistics

Recorded on 7 August 2026.

| Evidence | Record |
| --- | --- |
| Scope | JIOC, command, Ops and exact-team grants return only authorised organisational aggregates; Platform Administrator receives whole-platform metadata only |
| Measures | Traffic, work in progress, age, due risk, throughput, stage duration, clarification, rework, feedback and direct-child comparison |
| Privacy | No request, product, clarification, reason or Customer content enters the facts; feedback cohorts below five are suppressed |
| Frontend | Grant-aware navigation, bounded dates, time-zone control, projection freshness, accessible chart/table parity and empty/error states |
| Backend | 474 passed, 98.75% line and 95.51% branch coverage |
| Frontend | 161 passed, 99.37% line and 95.52% branch coverage |

## Expansion 5: Team workspace and roster lifecycle

Recorded on 7 August 2026. The roster slice closed first. Calendar, Board and
Planning evidence is recorded separately in Expansions 6 and 7 below.

| Evidence | Record |
| --- | --- |
| Decision | ADR 0011, effective-dated team membership |
| Threat model | `docs/threat-model/team-workspaces-and-calendars.md` |
| Migration | `0006_team_memberships`; empty upgrade, drift check, downgrade to `0005`, re-upgrade and second drift check passed |
| Authority | Active exact-team `ROSTER` grant for Manager changes; Analysts read only; sibling, ancestor and unrelated teams return not found |
| Lifecycle | Add existing active Analyst, reasoned end, scheduled one-winner transfer, effective projection and session-scope update |
| Safety | Active service work blocks end and transfer; stale versions conflict; management reasons are redacted from Analysts |
| Backend | `uv run --directory apps/api pytest -q`: 482 passed, 97.61% line and 95.00% branch coverage |
| Frontend | `pnpm --filter @istari-service/web test`: 166 passed, 99.41% line and 95.25% branch coverage |
| Static | Ruff format/check, mypy, TypeScript, ESLint, line-limit, terminology, OpenAPI and production build passed after test formatting correction |
| Safe disposition | Active requests, work packages, commitments and reservations block membership changes until reassigned, handed over or cancelled |

## Expansion 6: Canonical workforce calendar

Recorded on 7 August 2026.

| Evidence | Record |
| --- | --- |
| Decision | ADR 0008, one canonical event with personal and exact-team projections |
| Threat model | `docs/threat-model/team-workspaces-and-calendars.md` |
| Migration | `0007_canonical_calendar`; empty upgrade, drift check, downgrade to `0006`, re-upgrade and second drift check passed |
| Scope | Personal owner and exact current-team projection only; unrelated, cross-team and Platform Administrator access denied; organisational ancestors receive aggregate statistics |
| Privacy | Private and availability-only title and notes are redacted at persistence projection; team-detail remains exact-team scoped |
| Lifecycle | Timed and all-day events, IANA zones, daily and weekly recurrence, occurrence edit/cancel, future split and whole-event cancellation |
| Commitments | Exact-team Manager creation, subject acknowledgement or reasoned dispute, and roster-disposition blocking |
| Capacity | Calendar-backed working-minute preview, expiring single-use token, source digest and stale commit rejection |
| Backend | `uv run --directory apps/api pytest`: 506 passed, 97.30% line and 95.34% branch coverage |
| Frontend | `pnpm --filter @istari-service/web test`: 176 passed, 99.42% line and 95.05% branch coverage |
| Static | Ruff format/check, mypy, TypeScript and ESLint passed; focused axe calendar check passed |
| Remaining programme proof | PostgreSQL/Camunda Playwright journey, manual accessibility review, performance and recovery evidence remain Expansion 8 gates |

## Expansion 7: Workflow-derived board and agile planning

Recorded on 7 August 2026.

| Evidence | Record |
| --- | --- |
| Decision | ADR 0009, workflow-derived request cards and separately versioned work packages |
| Threat model | `docs/threat-model/team-workspaces-and-calendars.md` |
| Migration | `0008_team_agile_planning`; empty upgrade, previous-schema upgrade, drift check, downgrade, re-upgrade and second drift check passed |
| Board | Board and table projections cover waiting, ready, active, blocked, review, rework, hold and recent completion states; request cards move only through named Camunda commands |
| Planning | Versioned packages include owner, contributors, estimate, remaining effort, due date, priority, dependencies, blockers, acceptance criteria and immutable activity |
| Controls | Exact-team authority, optimistic versions, dependency-cycle rejection, WIP enforcement, saved views, keyset pagination, optional iterations and calendar-backed reservations |
| Roster safety | Active request, package, commitment and reservation counts block unsafe membership removal; Manager package handover moves the displayed workload to the replacement Analyst |
| Browser | Real React and FastAPI Manager journey created and moved a package, reassigned its owner, and verified the People workload and safe-removal state. It used isolated SQLite and the fake workflow port because Docker Desktop rejected the Windows workspace bind mount |
| Backend | `uv run --directory apps/api pytest`: 513 passed, 99.59% line and 97.48% branch coverage |
| Frontend | `pnpm --filter @istari-service/web test`: 183 passed, 99.41% line and 95.15% branch coverage |
| Static and security | Ruff format/check, mypy, TypeScript, ESLint, line-limit, terminology, production build, Bandit, Python dependency audit, production Node audit, BPMN validation, workflow smoke contract and Compose configuration passed |
| Remaining programme proof | Full current browser matrix on PostgreSQL and Camunda, manual accessibility, secret, licence and built-image scans, backup/restore, performance, recovery and stakeholder sign-off remain Expansion 8 gates |

## Expansion 8A: related records, privileged administration and operations

Recorded on 7 August 2026.

| Evidence | Record |
| --- | --- |
| Related records | Authorised manual search, typed duplicate/related/output links, append-only actor and reason history, exact scope enforcement, replay protection and output-release validation |
| Administrator step-up | Five-minute password-confirmed elevated session, sensitive mutation enforcement, CSRF and session isolation, expiry, wrong-password and non-Administrator denial tests, and locked React controls |
| Migrations | `0009_manual_related_records`, `0010_platform_admin_step_up` and `0011_operational_evidence`; empty, previous, downgrade, re-upgrade and drift checks passed in the isolated compatibility harness |
| Retention | Dry-run default, exact apply confirmation, state and age recheck, 1,000-record class bound, append-only content-free evidence and preservation of unresolved workflow state |
| Recovery controls | Validated custom-format PostgreSQL backup with checksum, empty-target restore guard and post-restore schema, count and tamper-chain verification scripts |
| Observability | Correlation-safe structured API telemetry plus database, Camunda, outbox, projection, backup-age and retention health snapshot with deterministic content-free alerts |
| Runbook | Supported hours, severity targets, alert thresholds, recovery, rollback and safe-diagnostic procedures; named pilot people remain an acceptance dependency |
| Automated evidence | Related-record, step-up, retention, restore-verification, operational-snapshot and telemetry tests; PowerShell operations contract; Ruff, mypy, line, terminology, TypeScript and ESLint gates |
| Remaining programme proof | Live PostgreSQL restore, alert and interruption rehearsals, browser/accessibility/performance matrices, security assurance scans and named stakeholder acceptance |

### Expansion 8A PostgreSQL and security addendum

PostgreSQL 17.9 passed empty, previous, downgrade, re-upgrade and drift migration
paths. Separate migration-owner, runtime and read-only backup roles passed access
probes, including runtime denial for schema creation and append-only mutation.
A custom archive restored into an empty isolated database, retained 72 synthetic
users, passed revision and both audit-chain checks, and completed verification in
1.22 seconds. Bandit, locked Python and Node dependency audits and the licence
gate also passed. Secret and built-image execution artefacts remain outstanding.
