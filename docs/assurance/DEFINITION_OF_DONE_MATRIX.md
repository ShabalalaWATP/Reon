# Definition of Done Matrix

## Purpose

This is the authoritative completion register for the ISTARI Service MVP. A row
closes only when its exact condition is proved by the named evidence. Historical
results remain in the expansion ledger; this matrix records the final aggregate
programme state.

Status values are `OPEN`, `IN PROGRESS`, `EVIDENCE READY` and `ACCEPTED`, as
defined in `docs/PROGRAMME_DEFINITIONS_OF_DONE.md`.

## Foundation and product gates

| Gate | Definition of done | Required evidence | Status |
| --- | --- | --- | --- |
| DOD-00 | All baseline product decisions have a named owner, decision, date and rationale | `docs/decisions/PILOT_BASELINE_DECISIONS.md` with no undecided row | OPEN |
| DOD-01 | Source control has an initial reviewed baseline and an approved private remote or a signed local-only exception | `docs/assurance/SOURCE_CONTROL_BASELINE.md`, remote record and decision entry | IN PROGRESS |
| DOD-02 | Every feature has an accepted specification, applicable ADR and threat-model coverage | Spec/ADR/threat-model traceability review | EVIDENCE READY |
| DOD-03 | Representative terminology is clean and every hand-written source file is at most 350 lines | `pnpm terminology` and `pnpm line-limit` | EVIDENCE READY |
| DOD-04 | Backend and frontend independently meet 95% line and branch coverage | Aggregate pytest and Vitest coverage reports | EVIDENCE READY |
| DOD-05 | Empty, previous-revision, downgrade, re-upgrade and drift migration rehearsals pass on PostgreSQL | `docs/assurance/MIGRATION_AND_RESTORE_EVIDENCE.md` | EVIDENCE READY |

## Functional gates

| Gate | Definition of done | Required evidence | Status |
| --- | --- | --- | --- |
| DOD-10 | Customer drafts, mandatory submission, dashboard tracking, authenticated release link and one-time feedback pass | API matrix and cross-browser Customer Playwright journey | EVIDENCE READY |
| DOD-11 | Analyst clarification is append-only, scoped, repeatable and returns to the same assignment through Camunda | API abuse matrix and live Camunda browser journey | EVIDENCE READY |
| DOD-12 | Manual related-record search returns authorised records only and stores typed links with actor, reason and history | Feature spec, migration, API/UI tests and scope-abuse tests | EVIDENCE READY |
| DOD-13 | Every configured route is selectable, separately staffed and completes without OSG fallback | OSG and alternative-branch PostgreSQL/Camunda journeys | EVIDENCE READY |
| DOD-14 | Analyst, Manager and QC production, rework, separation-of-duties and dissemination paths pass | Workflow/API tests and browser journeys | EVIDENCE READY |
| DOD-15 | Statistics expose only exact authorised scope and content-free aggregates | Cross-branch API oracle and chart/table browser review | EVIDENCE READY |
| DOD-16 | Team roster lifecycle preserves history and blocks unsafe removal or transfer | Concurrency, disposition, scope and Manager browser evidence | EVIDENCE READY |
| DOD-17 | Canonical calendars pass recurrence, privacy, commitment, DST and capacity behaviour | API/property tests and cross-browser calendar journey | EVIDENCE READY |
| DOD-18 | Workflow-derived boards and agile packages pass WIP, pagination, handover, iteration and capacity behaviour | API/concurrency tests and cross-browser board journey | EVIDENCE READY |
| DOD-19 | Platform administration manages identities safely without request-content access and sensitive actions use step-up authentication | API abuse tests and Administrator browser journey | EVIDENCE READY |

## Security and privacy gates

| Gate | Definition of done | Required evidence | Status |
| --- | --- | --- | --- |
| DOD-20 | Role, object, assignment, organisation and action policies deny every matrix abuse case at the server boundary | `docs/assurance/SECURITY_MATRIX_EVIDENCE.md` | EVIDENCE READY |
| DOD-21 | Session, CSRF, origin, throttling, disabled-account and replay controls pass | Automated security tests and browser negative cases | EVIDENCE READY |
| DOD-22 | Audit events are append-only in behaviour, HMAC-linked and independently verifiable | Integrity command, tamper test and PostgreSQL privilege evidence | EVIDENCE READY |
| DOD-23 | Logs, analytics and audit summaries contain no prohibited content | Redaction tests plus captured-log inspection | EVIDENCE READY |
| DOD-24 | Dependency, static, secret, container and licence scans have no unresolved high or critical finding | Versioned scan summary and raw local/CI artefacts | EVIDENCE READY |
| DOD-25 | Retention and deletion rules preserve required history and safely purge eligible data | Accepted policy, dry-run report, job tests and audit evidence | EVIDENCE READY |

## Accessibility, compatibility and performance gates

| Gate | Definition of done | Required evidence | Status |
| --- | --- | --- | --- |
| DOD-30 | Named pages have zero serious/critical axe findings and pass keyboard, focus, 200% zoom and reduced-motion review | `docs/assurance/ACCESSIBILITY_EVIDENCE.md` and screenshots | EVIDENCE READY |
| DOD-31 | Critical journeys pass current stable Chrome, Edge and Firefox at desktop and narrow widths | Versioned Playwright report and browser-version record | EVIDENCE READY |
| DOD-32 | Ordinary operations and bounded statistics/calendar/board reads meet programme latency and error thresholds | Reproducible load script and percentile report | EVIDENCE READY |
| DOD-33 | Loading, empty, error, stale, conflict and permission states are covered in each critical workspace | Component/API matrix and browser screenshots | EVIDENCE READY |

## Operations and recovery gates

| Gate | Definition of done | Required evidence | Status |
| --- | --- | --- | --- |
| DOD-40 | Health, structured logs, metrics and alerts cover database, Camunda, outbox, projections and backup age without content leakage | Runbook, metrics tests and alert rehearsal | EVIDENCE READY |
| DOD-41 | PostgreSQL backup and clean restore meet integrity and 30-minute rehearsal targets | Backup/restore script, clean database proof and evidence record | EVIDENCE READY |
| DOD-42 | Database and Camunda interruption recover without loss, duplicate records or invented state within 15 minutes | Controlled recovery scenarios and reconciliation evidence | EVIDENCE READY |
| DOD-43 | Support hours, incident ownership, severity, escalation, rollback and safe diagnostics are accepted | `docs/operations/SUPPORT_AND_INCIDENT_RUNBOOK.md` | IN PROGRESS |
| DOD-44 | Complete Customer, routing, Analyst, Manager, QC, statistics, roster, calendar, board and admin journeys pass on PostgreSQL and Camunda | Final Playwright HTML/JUnit artefacts | EVIDENCE READY |

## Acceptance gates

| Gate | Definition of done | Required evidence | Status |
| --- | --- | --- | --- |
| DOD-50 | Product owner accepts functionality and known limitations | Signed pilot record | OPEN |
| DOD-51 | Security owner accepts the threat models, matrix and residual risks | Signed pilot record | OPEN |
| DOD-52 | Operational owner accepts deployment, monitoring, backup, recovery and support | Signed pilot record | OPEN |
| DOD-53 | Representative users complete UAT and accept the service | Signed pilot record with scenarios and outcomes | OPEN |
| DOD-54 | Final requirement-by-requirement audit finds no missing, indirect or contradictory evidence | `docs/assurance/FINAL_COMPLETION_AUDIT.md` | OPEN |

## Required final command set

The exact tool versions and full output are retained in the evidence directory.
The minimum final command set is:

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/api --all-groups --frozen
pnpm check
pnpm --filter @istari-service/web test
pnpm --filter @istari-service/web build
uv run --directory apps/api ruff format --check .
uv run --directory apps/api ruff check .
uv run --directory apps/api mypy src
uv run --directory apps/api bandit -c pyproject.toml -r src alembic
uv run --directory apps/api pytest
pnpm smoke-contract
pwsh -File workflow/validate-bpmn.ps1
pwsh -File workflow/test-validator.ps1
docker compose config --quiet
```

Security, migration, browser, accessibility, performance, backup and recovery
commands are added to this set as their reproducible scripts are implemented.
