# Product Evolution Definition of Done Matrix

## Purpose

This register covers only the operational product evolution defined by
[`operational-product-evolution.md`](../specs/operational-product-evolution.md)
and planned in
[`NEXT_PRODUCT_EXPANSION_PLAN.md`](../NEXT_PRODUCT_EXPANSION_PLAN.md). It does not
replace or revise the accepted MVP
[`DEFINITION_OF_DONE_MATRIX.md`](DEFINITION_OF_DONE_MATRIX.md).

A gate closes only when its condition is proved by current, reproducible evidence
from the product-evolution implementation. Existing MVP evidence may establish a
baseline but cannot prove a new capability. Status values are `OPEN`, `IN
PROGRESS`, `EVIDENCE READY` and `ACCEPTED`. Every gate below starts `OPEN` and no
implementation or acceptance is implied by this document.

## Design and foundation gates

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-00 | The evolution specification, ADRs 0015–0017, permission matrix, recipient matrix and all named operational decisions are accepted by their owners | Dated approvals; decision register has no unresolved file, scanner, link-domain, approver, reminder, retention or export row | OPEN |
| PE-DOD-01 | Migrations 0012–0017 preserve existing identifiers and history, stable team assignment and the bounded legacy workflow identity | PostgreSQL empty/previous upgrade, drift, safe downgrade, re-upgrade, backfill-oracle and rollback reports; local SQLite rehearsal is complete | IN PROGRESS |
| PE-DOD-02 | New records remain inaccessible while their release flags are disabled and projections rebuild idempotently | API denial matrix plus duplicate-free projection rebuild and checkpoint evidence | IN PROGRESS |
| PE-DOD-03 | Every changed hand-written source file stays within 350 lines and the full repository passes format, lint, type, build, terminology, OpenAPI and BPMN checks | Hosted CI logs and exact local command transcript from the release candidate | EVIDENCE READY |
| PE-DOD-04 | Backend and frontend independently retain at least 95 per cent line and branch coverage | Release-candidate pytest and Vitest coverage reports with thresholds unchanged | EVIDENCE READY |

## Action workspace gates

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-10 | Every representative role completes its ordinary journey from `My work` using the same authorised results as its rollout-period queue | Positive role matrix and current Chrome, Edge and Firefox journeys for Customer, routing, Analyst, Manager, QC and Administrator roles | OPEN |
| PE-DOD-11 | Sibling, ancestor, unrelated, cross-Customer, revoked-grant, ended-membership and disabled-account action access is denied without disclosing object existence | Direct-identifier and list/deep-link API abuse matrix with non-disclosing responses | OPEN |
| PE-DOD-12 | Action pagination is stable under concurrent state changes and exposes bounded filters, saved views, source version and honest freshness | Concurrency oracle, keyset traversal tests and stale/conflict browser evidence | OPEN |
| PE-DOD-13 | No action row, saved view, board gesture or deep link can route, prioritise, assign, approve, disseminate or close work except through its named human use case | Server command-policy tests and audit trace proving explicit actor and authoritative transition | OPEN |

## Notification gates

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-20 | Every specified event creates exactly one notification for each permitted recipient under commit, replay, retry and concurrent repair | Event-by-recipient oracle, outbox replay tests and uniqueness evidence | OPEN |
| PE-DOD-21 | Notification list, count, preference, mark-read and archive behaviour is consistent, and action completion does not replace authoritative task state | API state-machine tests, UI journeys and source-state comparison | OPEN |
| PE-DOD-22 | Revocation, ended membership and account disablement remove live notification and deep-link access immediately while preserving content-free audit history | Access-loss browser/API scenarios and audit inspection | OPEN |
| PE-DOD-23 | Notification payloads, logs and metrics contain no request narrative, clarification text, product content, Customer identity, private calendar text, token or credential | Schema assertions, captured-log scan and representative event inspection | OPEN |
| PE-DOD-24 | Notifications become visible within ten seconds at pilot load and display measured lag when live refresh or projection delivery fails | Load percentile report, live-update interruption journey, polling fallback and reconciliation evidence | OPEN |

## Managed artefact and external-link gates

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-30 | Clean PDF, DOCX and PPTX artefacts pass upload intent, quarantine, validation, malware scan, Manager review, independent QC dissemination and Customer dashboard access | End-to-end API, object-store, scanner and three-browser journeys for each type | IN PROGRESS |
| PE-DOD-31 | Extension or magic-byte mismatch, macro, archive expansion, encryption, oversize, malware, timeout, unknown result and orphan uploads cannot reach review or dissemination | Format corpus results, scanner failure matrix and lifecycle database/object assertions | OPEN |
| PE-DOD-32 | Review and dissemination bind to one immutable package version and any artefact change invalidates earlier approval | Version/checksum concurrency tests and append-only dissemination audit trace | OPEN |
| PE-DOD-33 | Unreleased, cross-Customer, Administrator, unrelated-team, replaced, withdrawn and expired artefact access is denied on every attempt | Direct download/redirect abuse matrix and content-free allowed/denied access audit | OPEN |
| PE-DOD-34 | Released storage has no public access and downloads use short-lived grants or application streaming with safe filename, attachment disposition, `no-store` and `nosniff` | Bucket-policy inspection, unauthenticated object probe and response-header tests | OPEN |
| PE-DOD-35 | External products accept only normalised allow-listed HTTPS destinations, are never fetched by the backend, and require authenticated recipient re-authorisation | URL abuse corpus covering schemes, credentials, fragments, private hosts, disallowed domains and expiry; outbound-request assertion; safe-redirect browser evidence | OPEN |

## Organisation and workflow configuration gates

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-40 | A valid sibling branch can be drafted, validated, independently approved and activated without application code changes | Configuration history, different-actor step-up evidence and live PostgreSQL/Camunda route journey with distinct Manager and Analyst groups | IN PROGRESS |
| PE-DOD-41 | Validation rejects cycles, orphans, skipped levels, duplicate identifiers, invalid candidate groups and loss of every complete Customer-to-team route | Deterministic validation corpus and UI finding-to-unit links | OPEN |
| PE-DOD-42 | Concurrent edit or activation has one winner, and rollback uses a validated superseding version without rewriting history | Concurrency tests, immutable version audit and rollback rehearsal | OPEN |
| PE-DOD-43 | Declarative templates cannot add code, scripts, expressions or arbitrary BPMN, weaken mandatory fields, bypass a human stage or grant content access | Signed-schema negative corpus, incompatible BPMN denial and permission tests | OPEN |
| PE-DOD-44 | New requests use the activated snapshot while an existing request completes on its pinned organisation, form, workflow and notification-policy versions | Side-by-side live Camunda journeys and current-versus-as-of data oracle | OPEN |

## Planning and statistics gates

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-50 | Planning cockpit, templates, checklists, blocker ageing, dependencies, iterations and capacity scenarios preserve calendar, package, reservation and Camunda authority | Behaviour, dependency-cycle, WIP, reservation and workflow-state comparison tests | OPEN |
| PE-DOD-51 | Reassignment, handover and commitments are explicit Manager-led transactions; estimates never assign an Analyst, change priority or move a Camunda task | Concurrency and audit tests plus drag and keyboard-equivalent browser journeys | OPEN |
| PE-DOD-52 | Capacity remains correct across leave, recurrence, transfer, active work, reservations and disputed commitments at the agreed 5,000-occurrence and 2,500-package fixture | Fixed-fixture oracle, concurrency report and p95 performance result | OPEN |
| PE-DOD-53 | Every enhanced statistic is reproducible from versioned content-free facts and is scoped to exact active grants and historical organisation versions | Formula oracle; direct, descendant, ancestor, sibling, revoked and expired grant matrix; rebuild integrity report | OPEN |
| PE-DOD-54 | Charts, accessible tables, textual summaries and permitted aggregate CSV/PDF exports use the same rows, bounds, suppression and freshness | Screen/export parity tests, cohort boundary corpus, audit trace and content scan | OPEN |
| PE-DOD-55 | No statistic, export or planning view identifies or ranks an Analyst or contains request, product, Customer or private calendar content | Schema/static assertions, captured output review and negative privacy tests | OPEN |

## Security, accessibility and recovery gates

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-60 | All abuse cases in the four updated threat models have an assigned automated or manual test layer and no unresolved high or critical finding | Threat-to-test traceability and versioned dependency, static, secret, licence, container and object-scanner reports | IN PROGRESS |
| PE-DOD-61 | Every mutation enforces CSRF, trusted origin, active session, current role/scope, expected version and idempotency where retry can duplicate an effect | API security matrix and browser negative cases | OPEN |
| PE-DOD-62 | Product, notification, configuration, planning and analytics logs, metrics and audit metadata meet the documented minimisation rules | Captured-log and audit-field inspection with prohibited-value canaries | OPEN |
| PE-DOD-63 | `My work`, notifications, product review/release, configuration, planning and statistics pass keyboard, focus, 200 per cent zoom, reduced motion, chart-table parity and 390-pixel-width review with no serious or critical axe finding | Named-page accessibility record, axe reports, screenshots and keyboard transcripts | OPEN |
| PE-DOD-64 | Complete critical journeys pass current stable Chrome, Edge and Firefox at desktop and narrow widths | Versioned Playwright HTML/JUnit artefacts and browser-version record | OPEN |
| PE-DOD-65 | Ordinary bounded reads meet p95 below two seconds, notification visibility meets ten seconds and release download/error targets are accepted at pilot load | Reproducible load scripts, fixture declaration, percentile/error report and signed thresholds | OPEN |
| PE-DOD-66 | Database, Camunda, outbox, action/notification/analytics projections, object store and scanner interruptions recover without loss, duplication, invented success or unsafe release | Controlled fault matrix, reconciliation timings and quarantine assertions | OPEN |
| PE-DOD-67 | Database, object metadata, configuration and retained audit can be restored together and released objects are reconciled to metadata within accepted recovery targets | Empty-target restore rehearsal, integrity/count checks, object inventory comparison and owned recovery record | OPEN |
| PE-DOD-68 | Every enabled feature has a content-free health measure, owned alert, response target, safe runbook, release flag and rehearsed non-destructive rollback | Alert and runbook review, feature-flag exercise and superseding-configuration rollback evidence | OPEN |

## Acceptance gates

| Gate | Objective completion condition | Required evidence | Status |
| --- | --- | --- | --- |
| PE-DOD-70 | Product owner accepts every functional outcome, known limitation and staged rollout decision | Named, dated product-evolution acceptance record | OPEN |
| PE-DOD-71 | Security owner accepts the updated threat models, scan results and time-bounded residual risks | Named, dated security acceptance with owner and expiry for every accepted medium risk | OPEN |
| PE-DOD-72 | Operational owner accepts storage/scanner operation, monitoring, recovery, support, retention and rollback | Named, dated operational acceptance and completed rehearsal references | OPEN |
| PE-DOD-73 | Representative users from every role complete the new daily-work, notification, dissemination, configuration, planning and statistics scenarios applicable to them | Named UAT record with scenario, environment, result and unresolved issue count | OPEN |
| PE-DOD-74 | Final requirement-by-requirement review finds no missing, stale, indirect or contradictory evidence and hosted CI is clean for the accepted revision | Product-evolution completion audit mapping each specification outcome and gate to immutable evidence | OPEN |

Until every applicable row is `ACCEPTED`, the existing MVP remains the truthful
accepted product baseline and the evolution capabilities remain a non-production
local release candidate.
