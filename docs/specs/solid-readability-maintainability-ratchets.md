# SOLID, readability and maintainability improvement specification

Status: implemented and verified
Last reviewed: 18 August 2026

## Objective

Raise the codebase's evidenced SOLID adherence, readability and maintainability
to at least 8.5 out of 10 without replacing working behaviour with speculative
layers. The score is an assessment summary, not the acceptance mechanism. The
requirements and executable gates below determine completion.

## Baseline

The August 2026 review found strong external adapter boundaries, high automated
coverage and disciplined assurance documentation. It also found concrete
repository imports in application services, reverse repository-to-service
imports, import cycles, one 36-method repository protocol, dense frontend
orchestration and source files with little room below the 350-line hard limit.

Existing architecture tests protect thin routes and framework-free policy, but
did not stop these forms of coupling from increasing. This programme adds
ratchets before broad refactoring so every milestone leaves the codebase no
worse than it found it.

## Requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| SRM-01 | Application services must not add imports of concrete repositories, composition modules or SQLAlchemy | AST dependency ratchet with shrinking per-module debt counts |
| SRM-01A | HTTP routers must not add concrete persistence dependencies | AST router-import ratchet with shrinking per-module debt counts |
| SRM-02 | Repositories must not add reverse imports of application service modules | AST dependency ratchet with shrinking per-module debt counts |
| SRM-03 | Backend package import cycles must not increase and remediated cycles must be removed from the baseline | Deterministic strongly-connected-component test |
| SRM-04 | Application protocols contain at most 12 methods unless recorded as bounded debt | Protocol-width AST test and removal of the current broad product protocol |
| SRM-05 | New source retains refactoring headroom below 330 lines; existing files above that target cannot grow | Source-headroom ratchet plus the existing 350-line hard gate |
| SRM-06 | Browser network access and application API paths remain isolated in typed API adapters | Frontend source boundary test |
| SRM-07 | Protected TanStack Query keys are created by the central scoped-key factory | Literal protected-key debt ratchet and context-switch regression tests |
| SRM-08 | New frontend functions have complexity no greater than 12 and nesting depth no greater than four | ESLint plus an exact, shrinking per-file complexity baseline |
| SRM-09 | Refactors preserve object-level authorisation, audit semantics, idempotency and workflow authority | Existing security, PostgreSQL, workflow and browser behaviour tests |
| SRM-10 | Architecture debt is visible, monotonically reduced and never refreshed merely to make CI pass | Reviewed baseline changes linked to the remediating implementation |

## Target dependency direction

1. FastAPI routers translate HTTP data and call application use cases.
2. Application use cases depend on small ports and framework-free records.
3. SQLAlchemy, Camunda, storage, scanner and audit adapters implement those
   ports and are wired at an explicit composition boundary.
4. Repositories map persistence records without importing application services.
5. React views render and handle interaction. Feature hooks own server-state
   orchestration, and typed API adapters own network calls.

Imports may point inward through these steps. A use case must not reach through
one adapter to construct another, and an adapter must not import a service DTO
to satisfy its own persistence contract.

## Executable ratchet policy

Debt baselines describe current violations, not approved architecture. A gate
compares the complete measured result with its baseline:

- a new module or violation fails immediately;
- reducing a violation requires reducing or deleting its baseline entry in the
  same change;
- a file already above 330 lines may shrink without churn, but cannot exceed its
  recorded ceiling;
- a wide protocol may shrink without churn, but cannot gain methods;
- complexity exceptions have exact measured per-file maxima. Any improvement or
  regression fails until the baseline is reduced or the growth is rejected.

Changing a baseline without removing the associated dependency, cycle, broad
interface or readability debt is not remediation.

## Delivery sequence

### 1. Correctness and containment

- Bound conversation loading and unread aggregation.
- Make context rotation and audit evidence failure-atomic.
- Namespace protected browser state by the active actor context.
- Fence delayed conversation and mutation responses from a newly selected
  request or context.
- Make multi-file upload retries stable and idempotent.

### 2. Application boundaries

- Introduce narrow conversation reader, writer, audience and event ports.
- Split the broad product repository capability by package reading, upload,
  review accountability and release.
- Move concrete construction into composition modules.
- Remove repository-to-service DTO imports and backend cycles.

### 3. Frontend orchestration

- Extract authentication lifecycle, context switch and cross-tab synchronisation
  from the provider facade.
- Extract work queue, conversation and product upload controllers into feature
  hooks and pure state models.
- Keep components focused on rendering, accessible interaction and local form
  state.

### 4. Readability and release assurance

- Reduce every complexity exception to 12 or document a narrow remaining reason.
- Split source files until the 330-line debt map is empty.
- Apply repository-wide formatting only in a dedicated mechanical change after
  functional refactors settle.
- Exercise PostgreSQL migration round trips and one complete synthetic browser
  workflow in CI.

## Completion criteria

The programme is complete only when:

- service-to-infrastructure, router-to-persistence and repository-to-service
  debt maps are empty;
- backend import cycles are empty, apart from a separately justified ORM model
  registration mechanism if it cannot be removed safely;
- no application protocol exceeds 12 methods;
- the source-headroom debt map is empty;
- raw protected query-key debt is empty;
- all production frontend functions meet complexity 12 and depth four;
- backend and frontend line and branch coverage remain at least 95 per cent;
- the complete static, unit, PostgreSQL, workflow and browser gates pass on one
  clean immutable candidate.

## Current implementation evidence

Baseline reviewed on 14 August 2026.

The 18 August maintainability pass preserved these ratchets while removing the
production workflow fake, separating HTTP application composition from lifespan
initialisation, eliminating the remaining wide application ports and
consolidating duplicated frontend components, hooks, schemas and test fixtures.
It also connected bounded analytics repair commands and notification-projection
failure accounting to their runtime entry points. Static, architecture, backend,
frontend, independent quality and independent security checks passed for that
candidate; exact run evidence remains in the master plan and development story.

The source-level programme has reached its zero-debt target:

- no application service imports infrastructure or concrete composition;
- no HTTP router imports persistence;
- no repository imports an application service;
- no backend package import cycle remains;
- no application protocol exceeds 12 methods;
- no maintained source file exceeds 330 lines;
- no protected frontend query uses a raw, unscoped key; and
- no production frontend function exceeds complexity 12 or nesting depth four.

The backend now uses focused capability ports and explicit composition modules.
Product persistence is separated by package, artefact, review, release and
storage responsibility. The ORM registration cycle has been replaced
by a neutral base, shared enums and an explicit registry. The frontend has
separate session lifecycle, context-switch, work-queue, conversation, product
upload and feature-controller modules. Prettier, Ruff, strict MyPy, ESLint,
dead-code, line-limit and dependency-direction checks are executable gates.

Current measured assessment:

| Quality | Score | Principal evidence |
| --- | ---: | --- |
| SOLID adherence | 9.0/10 | Zero dependency/cycle/protocol debt; focused ports and explicit composition |
| Readability | 8.8/10 | Zero 330-line headroom debt; canonical formatting; complexity 12/depth four |
| Maintainability | 8.8/10 | Executable ratchets, 95 per cent independent coverage gates and end-to-end CI lanes |
| Overall | 8.9/10 | Reproducible source metrics rather than a score-only assertion |

The root quality gate, strict backend static checks, security scan, production
web build and complete frontend suite pass. The containerised PostgreSQL 0043 to
0047 round trip passed against PostgreSQL, including populated upgrade,
downgrade, re-upgrade, empty-database upgrade and metadata-drift checks. The
complete Chromium journey passed from Customer submission through JIOC, DIGOC,
NCGI-A Ops, OSG Team, Analyst production, Manager review, independent QC review
and release, Customer retrieval and acceptance. These runtime checks exposed and
then verified repairs for PostgreSQL locking, selected-route membership,
conversation mutation, managed-upload and product review read-after-write
defects. The immutable candidate therefore satisfies the runtime-evidence
criterion as well as the maintainability target.

## Non-goals

- No dependency-injection framework or service locator.
- No generic base repository added solely to reduce import counts.
- No broad formatting mixed with behavioural or architectural changes.
- No weakening of coverage, authorisation, audit or transaction tests.
- No claim that a subjective score alone proves completion.
