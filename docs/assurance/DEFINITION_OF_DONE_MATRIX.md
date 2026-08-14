# Definition of Done Matrix

## Purpose

This is the single authoritative completion register for ISTARI Service. The
`DOD` rows record aggregate programme gates. The `PE-DOD` rows retain the more
detailed current-capability conditions that support those aggregate gates. A row
closes only when its exact condition is proved by the named evidence. Historical
results belong in the [development story](../DEVELOPMENT_STORY.md), not in a
second competing completion register.

Status values are `OPEN`, `IN PROGRESS`, `EVIDENCE READY` and `ACCEPTED`, as
defined in the [programme Definitions of Done](../PROGRAMME_DEFINITIONS_OF_DONE.md).

## Foundation and product gates

| Gate | Definition of done | Required evidence | Status |
| --- | --- | --- | --- |
| DOD-00 | All baseline product decisions have a named owner, decision, date and rationale | `docs/decisions/PILOT_BASELINE_DECISIONS.md` with no undecided row | OPEN |
| DOD-01 | Source control has an initial reviewed baseline and an approved remote with recorded visibility, or a signed local-only exception | `docs/assurance/SOURCE_CONTROL_BASELINE.md`, remote record and decision entry | EVIDENCE READY |
| DOD-02 | Every feature has an accepted specification, applicable ADR and threat-model coverage | Spec/ADR/threat-model traceability review | EVIDENCE READY |
| DOD-03 | Representative terminology is clean and every hand-written source file is at most 350 lines | `pnpm terminology` and `pnpm line-limit` | EVIDENCE READY |
| DOD-04 | Backend and frontend independently meet 95% line and branch coverage | Aggregate pytest and Vitest coverage reports | EVIDENCE READY |
| DOD-05 | Empty, previous-revision, downgrade, re-upgrade and drift migration rehearsals pass on PostgreSQL | `docs/assurance/MIGRATION_AND_RESTORE_EVIDENCE.md` | EVIDENCE READY |

## Functional gates

| Gate | Definition of done | Required evidence | Status |
| --- | --- | --- | --- |
| DOD-10 | Customer drafts, mandatory submission, dashboard tracking, authenticated release link and one-time feedback pass | API matrix and cross-browser Customer Playwright journey | EVIDENCE READY |
| DOD-11 | Analyst clarification is append-only, scoped, repeatable and returns to the same assignment through Camunda | API abuse matrix and live Camunda browser journey | EVIDENCE READY |
| DOD-12 | Automatic all-field related-request matching returns authorised, explainable results and stores typed human decisions with actor, reason and history | Feature spec, migration, deterministic ranking, API/UI and scope-abuse tests | EVIDENCE READY |
| DOD-13 | Every configured route is selectable, separately staffed and completes without SSG fallback | SSG and alternative-branch PostgreSQL/Camunda journeys | EVIDENCE READY |
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
| DOD-30 | Named pages have zero serious/critical axe findings and pass keyboard, focus, 200% zoom and reduced-motion review | [Accessibility and WCAG 2.2 evidence](ACCESSIBILITY_EVIDENCE.md) and screenshots | EVIDENCE READY |
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
| DOD-50 | Product owner accepts functionality and known limitations | Signed [acceptance record](ACCEPTANCE_RECORD.md) | OPEN |
| DOD-51 | Security owner accepts the threat models, matrix and residual risks | Signed [acceptance record](ACCEPTANCE_RECORD.md) | OPEN |
| DOD-52 | Operational owner accepts deployment, monitoring, backup, recovery and support | Signed [acceptance record](ACCEPTANCE_RECORD.md) | OPEN |
| DOD-53 | Representative users complete UAT and accept the service | Signed [acceptance record](ACCEPTANCE_RECORD.md) with scenarios and outcomes | OPEN |
| DOD-54 | Final requirement-by-requirement audit finds no missing, indirect or contradictory evidence | `docs/assurance/FINAL_COMPLETION_AUDIT.md` | OPEN |

## Detailed current-capability gates

These `PE-DOD` rows provide the detailed proof behind the aggregate gates above.
They cover the current capabilities defined by the
[operational product specification](../specs/operational-product-evolution.md).
They do not create a second release baseline. An aggregate gate cannot be
accepted while an applicable detailed gate remains open.

### Design and foundation

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-00 | The evolution specification, applicable ADRs, permission matrix, recipient matrix and all named operational decisions are accepted by their owners | Dated approvals; decision register has no unresolved file, scanner, link-domain, approver, reminder, retention or export row | OPEN |
| PE-DOD-01 | Current migrations preserve identifiers and history, stable team assignment, bounded workflow identity, configuration evidence, durable worker state and metadata alignment | PostgreSQL empty/previous upgrade, drift, safe downgrade, re-upgrade, backfill-oracle and multi-store restore reports | IN PROGRESS |
| PE-DOD-02 | New records remain inaccessible while their release flags are disabled and projections rebuild idempotently | API denial matrix plus duplicate-free projection rebuild and checkpoint evidence | IN PROGRESS |
| PE-DOD-03 | Every changed hand-written source file stays within 350 lines and the full repository passes format, lint, type, build, terminology, OpenAPI and BPMN checks | Immutable commit and hosted CI logs | IN PROGRESS |
| PE-DOD-04 | Backend and frontend independently retain at least 95 per cent line and branch coverage | Immutable commit and hosted release-candidate reports | IN PROGRESS |

### Action workspace and notifications

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-10 | Every representative role completes its ordinary journey from `My assigned actions` using the same authorised results as its rollout-period queue | Positive role matrix and current Chrome, Edge and Firefox journeys for Customer, routing, Analyst, Manager, QC and Administrator roles | OPEN |
| PE-DOD-11 | Sibling, ancestor, unrelated, cross-Customer, revoked-grant, ended-membership and disabled-account action access is denied without disclosing object existence | Direct-identifier and list/deep-link API abuse matrix with non-disclosing responses | OPEN |
| PE-DOD-12 | Action pagination is stable under concurrent state changes and exposes bounded filters, saved views, source version and honest freshness | Concurrency oracle, keyset traversal tests and stale/conflict browser evidence | OPEN |
| PE-DOD-13 | No action row, saved view, board gesture or deep link can route, prioritise, assign, approve, disseminate or close work except through its named human use case | Server command-policy tests and audit trace proving explicit actor and authoritative transition | OPEN |
| PE-DOD-20 | Every specified event creates exactly one notification for each permitted recipient under commit, replay, retry and concurrent repair | Event-by-recipient oracle, outbox replay tests and uniqueness evidence | OPEN |
| PE-DOD-21 | Notification list, count, preference, mark-read and archive behaviour is consistent, and action completion does not replace authoritative task state | API state-machine tests, UI journeys and source-state comparison | OPEN |
| PE-DOD-22 | Revocation, ended membership and account disablement remove live notification and deep-link access immediately while preserving content-free audit history | Access-loss browser/API scenarios and audit inspection | OPEN |
| PE-DOD-23 | Notification payloads, logs and metrics contain no request narrative, clarification text, product content, Customer identity, private calendar text, token or credential | Schema assertions, captured-log scan and representative event inspection | OPEN |
| PE-DOD-24 | Notifications become visible within ten seconds at pilot load and display measured lag when live refresh or projection delivery fails | Load percentile report, live-update interruption journey, polling fallback and reconciliation evidence | OPEN |

### Managed products and external links

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-30 | Clean PDF, DOCX and PPTX products pass upload intent, quarantine, validation, malware scan, Manager review, independent QC dissemination and Customer dashboard access | End-to-end API, object-store, scanner and three-browser journeys for each type | IN PROGRESS |
| PE-DOD-31 | Extension or magic-byte mismatch, macro, archive expansion, encryption, oversize, malware, timeout, unknown result and orphan uploads cannot reach review or dissemination | Format corpus results, scanner failure matrix and lifecycle database/object assertions | OPEN |
| PE-DOD-32 | Review and dissemination bind to one immutable package version and any product change invalidates earlier approval | Version/checksum concurrency tests and append-only dissemination audit trace | OPEN |
| PE-DOD-33 | Unreleased, cross-Customer, Administrator, unrelated-team, replaced, withdrawn and expired product access is denied on every attempt | Direct download/redirect abuse matrix and content-free allowed/denied access audit | OPEN |
| PE-DOD-34 | Released storage has no public access and downloads use short-lived grants or application streaming with safe filename, attachment disposition, `no-store` and `nosniff` | Bucket-policy inspection, unauthenticated object probe and response-header tests | OPEN |
| PE-DOD-35 | External products accept only normalised allow-listed HTTPS destinations, are never fetched by the backend, and require authenticated recipient re-authorisation | URL abuse corpus, outbound-request assertion and safe-redirect browser evidence | OPEN |

### Organisation and workflow configuration

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-40 | A valid sibling branch can be proposed, validated, independently approved and activated without application code changes | Configuration history, different-actor step-up evidence and live PostgreSQL/Camunda route journey with distinct Manager and Analyst groups | IN PROGRESS |
| PE-DOD-41 | Validation rejects cycles, orphans, skipped levels, duplicate identifiers, invalid candidate groups and loss of every complete Customer-to-team route | Deterministic validation corpus and UI finding-to-unit links | OPEN |
| PE-DOD-42 | Concurrent edit or activation has one winner, and rollback uses a validated superseding version without rewriting history | Concurrency tests, immutable version audit and rollback rehearsal | OPEN |
| PE-DOD-43 | Declarative templates cannot add code, scripts, expressions or arbitrary BPMN, weaken mandatory fields, bypass a human stage or grant content access | Signed-schema negative corpus, incompatible BPMN denial and permission tests | OPEN |
| PE-DOD-44 | New requests use the activated snapshot while an existing request completes on its pinned organisation, form, workflow and notification-policy versions | Side-by-side live Camunda journeys and current-versus-as-of data oracle | OPEN |
| PE-DOD-45 | Administrators can find a unit by name, code or kind, retain ancestor context, follow a keyboard breadcrumb and select only effective structurally valid parents without relying on the browser for security | Component, axe, forged-parent, stale-edit, 2,000-unit performance, 390-pixel and three-browser evidence | IN PROGRESS |

### Work packages and statistics

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-50 | Internal Work Package cards, blockers, dependencies and capacity views preserve calendar, package and Camunda authority | Behaviour, dependency-cycle, WIP and workflow-state comparison tests | OPEN |
| PE-DOD-51 | Reassignment, handover and commitments are explicit Manager-led transactions; estimates never assign an Analyst, change priority or move a Camunda task | Concurrency and audit tests plus drag and keyboard-equivalent browser journeys | OPEN |
| PE-DOD-52 | Capacity remains correct across leave, recurrence, transfer, active work, reservations and disputed commitments at the agreed scale fixture | Fixed-fixture oracle, concurrency report and p95 performance result | OPEN |
| PE-DOD-53 | Every enhanced statistic is reproducible from versioned content-free facts and is scoped to exact active grants and historical organisation versions | Formula oracle, scope matrix and rebuild integrity report | OPEN |
| PE-DOD-54 | Charts, accessible tables, textual summaries and permitted aggregate CSV/PDF exports use the same rows, bounds, suppression and freshness | Screen/export parity tests, cohort boundary corpus, audit trace and content scan | OPEN |
| PE-DOD-55 | No statistic, export or planning view identifies or ranks an Analyst or contains request, product, Customer or private calendar content | Schema/static assertions, captured output review and negative privacy tests | OPEN |

### Security, accessibility and recovery

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-60 | All abuse cases in the current threat models have an assigned automated or manual test layer and no unresolved high or critical finding | Threat-to-test traceability and versioned dependency, static, secret, licence, container and object-scanner reports | IN PROGRESS |
| PE-DOD-61 | Every mutation enforces CSRF, trusted origin, active session, current role/scope, expected version and idempotency where retry can duplicate an effect | API security matrix and browser negative cases | OPEN |
| PE-DOD-62 | Product, notification, configuration, planning and analytics logs, metrics and audit metadata meet the documented minimisation rules | Captured-log and audit-field inspection with prohibited-value canaries | OPEN |
| PE-DOD-63 | `My assigned actions`, notifications, product review/release, configuration, planning and statistics pass keyboard, focus, 200 per cent zoom, reduced motion, chart-table parity and 390-pixel-width review with no serious or critical axe finding | [Accessibility evidence](ACCESSIBILITY_EVIDENCE.md), axe reports, screenshots and keyboard transcripts | OPEN |
| PE-DOD-64 | Complete critical journeys pass current stable Chrome, Edge and Firefox at desktop and narrow widths | Versioned Playwright HTML/JUnit artefacts and browser-version record | OPEN |
| PE-DOD-65 | Ordinary bounded reads meet p95 below two seconds, notification visibility meets ten seconds and release download/error targets are accepted at pilot load | Reproducible load scripts, fixture declaration, percentile/error report and signed thresholds | OPEN |
| PE-DOD-66 | Database, Camunda, outbox, projections, object store and scanner interruptions recover without loss, duplication, invented success or unsafe release | Controlled fault matrix, reconciliation timings and quarantine assertions | OPEN |
| PE-DOD-67 | Database, object metadata, configuration and retained audit can be restored together and released objects are reconciled to metadata within accepted recovery targets | Empty-target restore rehearsal, integrity/count checks, object inventory comparison and owned recovery record | OPEN |
| PE-DOD-68 | Every enabled feature has a content-free health measure, owned alert, response target, safe runbook, release flag and rehearsed non-destructive rollback | Alert and runbook review, feature-flag exercise and superseding-configuration rollback evidence | OPEN |

### Detailed acceptance

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-70 | Product owner accepts every functional outcome, known limitation and staged rollout decision | Named, dated [acceptance record](ACCEPTANCE_RECORD.md) | OPEN |
| PE-DOD-71 | Security owner accepts the updated threat models, scan results and time-bounded residual risks | Named, dated [acceptance record](ACCEPTANCE_RECORD.md) with owner and expiry for every accepted medium risk | OPEN |
| PE-DOD-72 | Operational owner accepts storage/scanner operation, monitoring, recovery, support, retention and rollback | Named, dated [acceptance record](ACCEPTANCE_RECORD.md) and completed rehearsal references | OPEN |
| PE-DOD-73 | Representative users from every role complete the daily-work, notification, dissemination, configuration, planning and statistics scenarios applicable to them | Named UAT results in the [acceptance record](ACCEPTANCE_RECORD.md) | OPEN |
| PE-DOD-74 | Final requirement-by-requirement review finds no missing, stale, indirect or contradictory evidence and hosted CI is clean for the accepted revision | [Final completion audit](FINAL_COMPLETION_AUDIT.md) mapped to immutable evidence | OPEN |

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
