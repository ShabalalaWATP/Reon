# Mist Service Master Implementation Plan

## Current position, 15 August 2026

The delivered system is the complete local synthetic application: React web
client, FastAPI backend, PostgreSQL 17, Camunda 8.9 and ClamAV, running end to
end through Compose. This is a local-first synthetic build, not a production
deployment.

Session-verified regression evidence:

- 1,323 backend tests passing (13 skipped) at 98.13 per cent line and branch
  coverage.
- 542 frontend tests passing at 98.81 per cent line and 95.06 per cent branch
  coverage.
- Every locally runnable repository gate green: formatting, lint, type,
  dead-code, line-limit, documentation, terminology, OpenAPI contract,
  complexity and quality-gate self-tests. The licence gate is verified in CI;
  its local run was blocked by a machine-specific pnpm store fault, not by the
  repository.

The newest applied migration is `0047_saved_action_view_contexts.py`,
following `0045_notification_preference_contexts.py` and
`0046_product_package_policy.py` (`apps/api/alembic/versions`).

Remaining decisions before a connected or production deployment, identity
provider, hosting, secrets management, a distinct migration owner, staging
penetration evidence and named acceptance, are tracked in the
[enterprise readiness gap register](ENTERPRISE_READINESS_GAP_REGISTER.md) and
summarised under
[Production readiness, intentionally separate](#production-readiness-intentionally-separate)
below.

Use the [Contents](#contents) table to navigate. Sections further down record
how the system reached this position; several carry evidence numbers and
status wording that were accurate only when written. Those are corrected in
place rather than deleted, since they remain a useful record of delivery
history.

## Contents

This plan combines a static baseline (product principles, phases, gates) with
a chronological log of dated delivery milestones recorded as work completed.
The log is not laid out in strict chronological order; use the dates below,
not position in the file, to judge recency.

| Section | Date |
| --- | --- |
| [Current position](#current-position-15-august-2026) | 15 Aug 2026 |
| [Authentication, coordination and maintainability remediation](#authentication-coordination-and-maintainability-remediation-15-august-2026) | 15 Aug 2026 |
| [Current-state documentation and resource hygiene](#current-state-documentation-and-resource-hygiene-14-august-2026) | 14 Aug 2026 |
| [Current team workspace](#current-team-workspace-11-august-2026) | 11 Aug 2026 |
| [Current documentation authority](#current-documentation-authority-10-august-2026) | 10 Aug 2026 |
| [Accessibility plan and evidence](#accessibility-plan-and-evidence-11-august-2026) | 11 Aug 2026 |
| [SOLID and Secure by Design improvement programme](#solid-and-secure-by-design-improvement-programme-11-august-2026) | 11 Aug 2026 |
| [Customer navigation restraint](#customer-navigation-restraint-11-august-2026) | 11 Aug 2026 |
| [Route lifecycle tracking and analytical presentation](#route-lifecycle-tracking-and-analytical-presentation-10-august-2026) | 10 Aug 2026 |
| [GitHub quality and dependency automation](#github-quality-and-dependency-automation-9-august-2026) | 9 Aug 2026 |
| [Operational assurance and documentation maintenance](#operational-assurance-and-documentation-maintenance-8-august-2026) | 8 Aug 2026 |
| [Outcome](#outcome) | Reference |
| [Evidence and handling](#evidence-and-handling) | Reference |
| [Product principles](#product-principles) | Reference |
| [Architecture baseline](#architecture-baseline) | Reference |
| [Baseline decisions for implementation](#baseline-decisions-for-implementation) | Reference |
| [Phase 0: Repository and decision foundation](#phase-0-repository-and-decision-foundation) | Phase gate |
| [Phase 1: Reproducible secure platform](#phase-1-reproducible-secure-platform) | Phase gate |
| [Phase 2: Customer intake and visibility](#phase-2-customer-intake-and-visibility) | Phase gate |
| [Phase 3: JIOC and request coordination](#phase-3-jioc-and-request-coordination) | Phase gate |
| [Phase 4: Camunda routing and resilience](#phase-4-camunda-routing-and-resilience) | Phase gate |
| [Phase 5: Ops routing and product delivery](#phase-5-ops-routing-and-product-delivery) | Phase gate |
| [Phase 6: Manager check, QC, dissemination and feedback](#phase-6-manager-check-qc-dissemination-and-feedback) | Phase gate |
| [Phase 7: Supporting administration and operations](#phase-7-supporting-administration-and-operations) | Phase gate |
| [Phase 8: Assurance, pilot and hand-off](#phase-8-assurance-pilot-and-hand-off) | Phase gate |
| [Security verification matrix](#security-verification-matrix) | Reference |
| [Pilot scenarios](#pilot-scenarios) | Reference |
| [Pilot measures](#pilot-measures) | Reference |
| [Delivered: expansion programme (Expansions 0 to 8)](#delivered-expansion-programme-expansions-0-to-8) | Delivered |
| [Delivered: expanded product capabilities](#delivered-expanded-product-capabilities) | Delivered |
| [Production readiness, intentionally separate](#production-readiness-intentionally-separate) | Reference |
| [Capabilities outside the implemented baseline](#capabilities-outside-the-implemented-baseline) | Reference |
| [Definition of complete](#definition-of-complete) | Reference |
| [Guided configuration and enterprise documentation milestone](#guided-configuration-and-enterprise-documentation-milestone) | 7 Aug 2026 |
| [Operator orientation and factual timing milestone](#operator-orientation-and-factual-timing-milestone) | 8 Aug 2026 |
| [Maintainability and portable evaluation milestone](#maintainability-and-portable-evaluation-milestone) | 8 Aug 2026 |
| [Simplicity and runtime-efficiency deep dive](#simplicity-and-runtime-efficiency-deep-dive) | 8 Aug 2026 |
| [August security-remediation milestone](#august-security-remediation-milestone) | 9 Aug 2026 |
| [Unified organisation workspace milestone](#unified-organisation-workspace-milestone) | 9 Aug 2026 |
| [Access assistance and global classification milestone](#access-assistance-and-global-classification-milestone) | 10 Aug 2026 |
| [Explainable related-request matching milestone](#explainable-related-request-matching-milestone) | Undated |
| [Action-oriented team workspace milestone](#action-oriented-team-workspace-milestone) | 10 Aug 2026 |
| [Role-aware action navigation milestone](#role-aware-action-navigation-milestone) | 10 Aug 2026 |
| [Compact previous-request evidence milestone](#compact-previous-request-evidence-milestone) | 10 Aug 2026 |
| [Workspace-authority identity milestone](#workspace-authority-identity-milestone) | 10 Aug 2026 |
| [Personalised overview and primary-navigation milestone](#personalised-overview-and-primary-navigation-milestone) | 10 Aug 2026 |
| [Explicit personal-calendar visibility milestone](#explicit-personal-calendar-visibility-milestone) | 10 Aug 2026 |
| [Plain-language request coordination milestone](#plain-language-request-coordination-milestone) | 10 Aug 2026 |
| [Separated delivery-board milestone](#separated-delivery-board-milestone) | 13 Aug 2026 |
| [Request-tracking journey milestone](#request-tracking-journey-milestone) | 13 Aug 2026 |
| [Routing workspace monitoring and Customer acceptance milestone](#routing-workspace-monitoring-and-customer-acceptance-milestone) | 13 Aug 2026 |
| [Deterministic post-login landing fix](#deterministic-post-login-landing-fix) | 13 Aug 2026 |
| [Live QA readiness and route assurance](#live-qa-readiness-and-route-assurance) | 14 Aug 2026 |
| [Workflow runtime reliability remediation](#workflow-runtime-reliability-remediation) | 14 Aug 2026 |
| [SOLID, readability and maintainability programme](#solid-readability-and-maintainability-programme) | 14 Aug 2026 |

## Authentication, coordination and maintainability remediation, 15 August 2026

Status: implemented and verified locally on 15 August 2026.

- [x] Close the authentication lockout regression: public sign-in no longer
  writes account lock fields.
- [x] Make shared-pool object scope fail closed, with explicit membership
  evidence required rather than assumed.
- [x] Deduplicate outbox lease fencing and retry backoff into one shared
  module.
- [x] Make concurrent duplicate request submission idempotent.
- [x] Make coordination schemas strict.
- [x] Extend the architecture width checker to count inherited Protocol
  methods. This exposed nine wide union ports, now measured and capped in the
  shrink-only architecture debt baseline rather than hidden from it.
- [x] Add frontend payload validation, a route-scoped error boundary, route
  announcement accessibility (page titles and focus), account menu focus
  handling, a conversation polling gate and a paged actions cache key split.
- [x] Correct documentation: the pnpm version, the `--env-file` FastAPI start
  command, local start guidance, QC Manager naming and single-test guidance.

Evidence: see [Current position](#current-position-15-august-2026) for the
resulting aggregate test and coverage figures.

## Current-state documentation and resource hygiene, 14 August 2026

- [x] Reconcile the README, architecture, workflow, user stories, role matrix,
  assurance and deployment guides with the executable dual-context product.
- [x] Document the full dependency baseline and PostgreSQL, Camunda, storage,
  conversation, package, review, release and acceptance boundaries.
- [x] Expand the Structurizr source with component, dynamic and deployment views
  and validate it with the official CLI.
- [x] Provide one setup authority for Windows, Intel and Apple-silicon MacBook,
  Linux, AWS and Google Cloud synthetic environments.
- [x] Add a source-reference and stale-current-state documentation gate.
- [x] Close the quarantine-index SQLite test connection deterministically and
  make resource and unraisable-exception warnings fail backend tests.

## Current team workspace, 11 August 2026

- [x] Use the named workspace as the single sidebar destination when a current
  workspace is available.
- [x] Embed the established actionable queue as an exact-unit workspace view.
- [x] Present routing and delivery work through role-appropriate current tabs.
- [x] Keep workflow request cards separate from collapsible internal Work Package cards.
- [x] Retain standalone role queues for notification deep links and staff without
  a current workspace.
- [x] Update architecture, user stories, specification and regression coverage.

## Current documentation authority, 10 August 2026

- [x] Present the running product, active terminology and available interface
  directly.
- [x] Keep development chronology in `DEVELOPMENT_STORY.md`; keep current
  product behaviour in the README, architecture, workflow, user stories,
  specifications and operating guides.
- [x] Maintain one complete synthetic account directory containing all 108
  accounts, usernames, roles, memberships and Manager or Member positions.
- [x] Provide separate readable views for system context, containers, routing,
  delivery, durable workflow commands and the organisation hierarchy, together
  with an editable Structurizr model containing component and deployment views.
- [x] Document the complete human-led Camunda BPMN path, clarification and
  rework loops, assigned-Analyst controls, separate QC review and release,
  Customer acceptance and feedback.
- [x] Keep current application screenshots alongside browser evidence and
  refresh them whenever the corresponding surface changes materially.
- [x] Enforce documentation links, duplication, current terminology and image
  validity through repository checks.

## Accessibility plan and evidence, 11 August 2026

- [x] Design towards WCAG 2.2 Level AA with semantic structure, keyboard
  operation, visible focus, reduced-motion support, accessible chart-table
  parity and reflow down to 320 CSS pixels.
- [x] Maintain one current technical authority in the
  [accessibility and WCAG 2.2 evidence](assurance/ACCESSIBILITY_EVIDENCE.md).
- [x] Make accessibility discoverable from the root README, documentation home,
  [programme Definition of Done](PROGRAMME_DEFINITIONS_OF_DONE.md#user-experience-and-accessibility),
  [completion matrix](assurance/DEFINITION_OF_DONE_MATRIX.md#accessibility-compatibility-and-performance-gates)
  and [production gates](deployment/PRODUCTION_GATES.md).
- [x] Keep automated component, contrast, axe, keyboard, focus and reflow checks
  as release evidence without treating automation as human acceptance.
- [ ] Complete named keyboard, screen-reader, zoom, text-spacing,
  forced-colours, cognitive and representative-user reviews before claiming
  WCAG conformance or production acceptance.

## SOLID and Secure by Design improvement programme, 11 August 2026

- [x] Record a bounded first milestone for the external workflow runtime, with
  explicit dependency-direction, failure and credential-handling criteria.
- [x] Move Camunda SDK construction and lifecycle into one managed
  infrastructure adapter shared by the API and independent worker.
- [x] Make worker composition depend on the narrow `WorkflowEngine` port and add
  an architecture test that prevents process entry points importing the SDK.
- [x] Add broader dependency fitness tests for framework-free domain policy,
  thin HTTP routes and repository-only SQLAlchemy access, introducing no new
  layers unless they protect a real boundary.
- [x] Consolidate core request and active-work object/action authorisation behind
  typed policy decisions, then exercise cross-role, cross-route and
  direct-identifier denial matrices at the API boundary. Retain scoped database
  queries as independent defence in depth and keep the separate administration,
  statistics, planning and workspace grant models bounded to their own objects.
- [x] Separate remaining high-change service coordinators by use case, starting
  with configuration and product transfer, while retaining transaction and
  audit ownership in one explicit application boundary.
- [x] Replace remaining unstructured security-relevant dictionaries at external
  and audit boundaries with validated types, preserving forward-compatible
  evidence fields where required.
- [x] Complete independent architecture, code-quality and cyber-security review,
  full coverage gates, PostgreSQL/Camunda recovery checks and updated assurance
  evidence before closing the programme.

## Customer navigation restraint, 11 August 2026

- [x] Limit Customer primary navigation to `My requests` and `New request`.
- [x] Remove Customer calendar and organisation-directory links without changing
  staff navigation.
- [x] Route-gate direct Customer access to those staff destinations and return
  the account safely to `My requests`.
- [x] Update navigation, calendar, user-story, permission and architecture
  authorities and add role-regression coverage.

## Route lifecycle tracking and analytical presentation, 10 August 2026

- [x] Make request title the primary tracking identity while retaining linked
  references, ownership, required date and submission date.
- [x] Show the selected organisation route and delivery lifecycle for every
  request visible to an exact JIOC, command or Ops route member.
- [x] Add a direct, read-only historical detail route whose backend query repeats
  route membership and whose schema excludes actions, clarification, feedback
  and product content.
- [x] Add current-status, due-risk and active-age donut charts and a median-to-
  90th-percentile stage-duration graphic without creating a new analytics or
  authorisation path.
- [x] Retain labelled legends, content-free summaries, accessible table parity,
  keyboard focus and reduced-motion behaviour.
- [x] Pass backend and frontend coverage gates, repository quality gates,
  production build, live JIOC link navigation and browser console review.

## GitHub quality and dependency automation, 9 August 2026

- [x] Replace the Windows-only secure-production test path with a portable
  absolute temporary path so the Linux backend gate exercises the intended rules.
- [x] Align the repository with Dependabot's native `uv` ecosystem and supported
  pnpm 10 lockfile processing.
- [x] Add Dependabot coverage for security-tool Dockerfiles and root Compose
  references.
- [x] Run Actionlint, the OpenAPI consumer contract, current-source Gitleaks and
  gated reachable-history scanning in GitHub Actions.
- [x] Stage Gitleaks input from the exact tracked-file inventory so force-added
  files cannot be hidden by Docker ignore rules.
- [x] Add weekly execution, explicit job deadlines and retained coverage and
  secret-scan evidence.
- [x] Put Actionlint under Docker dependency automation and protect the split
  container workflow with a semantic image, migration, SBOM and teardown contract.
- [x] Exclude locally built Compose output tags from registry lookups while
  retaining update coverage for the external Compose bootstrap image.
- [x] Extend source line enforcement to custom Dockerfiles and the workspace
  manifest, and audit locked development/test tooling as well as runtime packages.
- [x] Confirm the repaired workflow and all Dependabot update jobs on GitHub
  after the change reaches `main`.

## Operational assurance and documentation maintenance, 8 August 2026

- [x] Exercise all privileged maintenance command dispatch branches.
- [x] Exercise PostgreSQL role validation, reviewed grant execution, dialect
  rejection and guaranteed engine disposal.
- [x] Establish one authoritative complete synthetic-account directory and test
  it against all 108 seeded identities.
- [x] Maintain one roster authority and an automated long-form documentation
  duplication gate.
- [x] Prove that Markdown documentation is exempt from the hand-written source
  line limit.

## Outcome

Deliver a secure, deliberately limited service-request product outside Coeus.
It uses Mist's visual character, a structured mandatory request form, a
Customer-owned status dashboard and a named human workflow.

This plan distinguishes the foundational vertical slice from the complete pilot
MVP. Working screens are not the exit condition. The pilot MVP is complete only
when functional, access, audit, recovery, accessibility and operational evidence
all meet the gates below.

The active expansion programme is governed by
[Programme Definitions of Done](PROGRAMME_DEFINITIONS_OF_DONE.md). A checklist
entry in this plan may be checked only when the corresponding evidence ledger is
complete. Final aggregate status is governed by the stable gates in the
[Definition of Done Matrix](assurance/DEFINITION_OF_DONE_MATRIX.md); a historical
phase result cannot substitute for a current aggregate gate.

## Evidence and handling

The plan combines:

- the Mist visual system, interaction patterns and synthetic users;
- the supplied MVP definition, reviewed as a sensitive source;
- current official Camunda release and integration guidance;
- secure-by-design, SOLID and repository quality requirements.

No source document, derived render, organisational detail or sensitive wording is
copied into this public-safe repository. Only generic product and assurance
requirements are retained.

### Source-to-plan traceability

| Source section | Programme effect |
| --- | --- |
| Non-functional requirements, page 14 | Accessibility, response time, audit, resilience and support become measured exit gates in Phases 1 and 8 |
| Security requirements, page 15 | Object-level access, session controls, safe content handling and defensive testing are mandatory design work, not a later hardening phase |
| Validation approach, page 18 | Pilot scenarios cover each persona, alternative routes, rework, negative access cases and workflow recovery |
| Exit criteria, page 19 | Completion needs functional, operational, security, accessibility and user evidence rather than a successful walkthrough alone |
| Decisions and assumptions, pages 20–21 | Unconfirmed ownership, service targets, identity, hosting and handling choices stay visible in the baseline decision and production-readiness registers |

## Product principles

- One structured record is the source of truth from draft through dissemination.
- All categorisation, priority, routing, allocation, acceptance, approval and
  dissemination decisions are made by named people.
- The first operational path is JIOC → DIGOC → NCGI-A Ops → OSG Team. Every
  synthetic sibling is staffed, selectable and receives its own Camunda task.
  Later staffing gaps wait visibly instead of borrowing OSG Team users.
- Customers see only their records. Staff see only records within their role,
  scope and assignment.
- The Platform Administrator manages identity, role and safe configuration
  metadata, with no implicit access to request content.
- Camunda owns process position and user-task lifecycle. Product PostgreSQL owns
  business content, identity, assignment, audit and the stable read model.
- Security policy is enforced in backend queries and mutations, never only in UI.
- Accessibility, observability, recovery and support are acceptance criteria, not
  deferred polish.
- Each phase closes its tests and evidence before the next phase becomes complete.

## Architecture baseline

```mermaid
flowchart LR
  Browser["React application"] --> API["FastAPI delivery layer"]
  API --> UseCases["Application use cases"]
  UseCases --> Domain["Domain policy"]
  UseCases --> Ports["Narrow ports"]
  Ports --> AppDB["Product PostgreSQL 17"]
  Ports --> Outbox["Transactional outbox"]
  Outbox --> Camunda["Camunda 8.9 user tasks"]
```

Dependencies point towards domain rules. FastAPI, SQLAlchemy, Camunda and React
are replaceable delivery or infrastructure details. The concrete rules are in
[System architecture](architecture/SYSTEM_ARCHITECTURE.md) and
[ADR 0002](adr/0002-secure-modular-foundations.md). The recoverable boundary for
claims and completions is fixed by
[ADR 0003](adr/0003-durable-human-workflow-commands.md).

## Baseline decisions for implementation

These safe defaults unblock the build but require sponsor confirmation before the
pilot:

| Topic | Baseline |
| --- | --- |
| Submitted edits | Submitted revisions are immutable; corrections append history |
| Manager check | Team Manager reviews Analyst work and cannot approve their own output |
| Outputs | Plain text and controlled references only; binary files excluded |
| Release | Explicit human action makes an approved output visible to authorised recipients |
| Scope | Customer area for Customers; delivery team or shared queue for staff |
| Intake schema | The thirteen fields in the approved product spec are mandatory |
| Priority and dates | JIOC sets priority; Customer gives required date and reason; no automatic service target |
| Notifications | In-app states only for MVP |
| Related work | People search and record links; no automated matching |
| Organisation | JIOC is the root; all configured children route and every team has a synthetic Manager and Analyst; OSG Team has three Managers and seven Analysts |

The hierarchy, post-delivery assurance path and safe activation rules are defined in
[Organisation and Routing](architecture/ORGANISATION_AND_ROUTING.md) and
[ADR 0004](adr/0004-data-driven-organisational-routing.md).

## Phase 0: Repository and decision foundation

- [x] Create the sibling repository at `C:\AlexDev\Mist-Service`.
- [x] Confirm that the Coeus worktree remains unchanged.
- [x] Audit Mist login, shell, dashboards, queues, tokens and user fixtures.
- [x] Define representative terminology, primary roles and supporting admin role.
- [x] Record application/workflow ownership, secure modular boundaries and threats.
- [x] Pin local Camunda 8.9.14 and PostgreSQL 17 architecture.
- [ ] Record sponsor confirmation or an explicit exception for each baseline
  decision above.
- [x] Select the GitHub repository and record its visibility and publication
  authority.
- [x] Create and secret-scan the reviewed local root commit before any remote
  publication.

Exit: vocabulary, scope, authorities, risks and product decisions are traceable.

## Phase 1: Reproducible secure platform

- [x] Scaffold React, FastAPI, Alembic, BPMN, local Compose and CI.
- [x] Use typed configuration and refuse mock users or weak cookie settings outside
  local mode.
- [x] Create separate product and Camunda database identities. A distinct migration
  owner and insert-only audit role remain a pilot-hardening item.
- [x] Add Argon2id credentials, opaque server-side sessions, CSRF, trusted origins,
  expiry, logout, generic failures, disabled accounts and bounded login attempts.
- [x] Maintain the complete Scottish-player identity directory, including the
  independent configuration approver; all local logons remain sequential and
  clearly marked as fictional.
- [x] Add liveness, dependency-aware readiness and correlation identifiers without
  logging content.
- [x] Prove migrations from empty and previous schema states.

Exit: installs are reproducible; auth, migration, static, line and terminology
gates pass; non-local insecure configuration fails closed.

## Phase 2: Customer intake and visibility

- [x] Port the Mist login composition and restrained application shell using
  neutral service language and reduced-motion-safe animation.
- [x] Let a Customer save, resume, edit and delete their own draft.
- [x] Validate the complete form in Zod for usability and Pydantic authoritatively.
- [x] Submit one immutable revision and one workflow-start outbox command in the
  same product-database transaction.
- [x] Show Customer-owned active, needs-input, completed and closed views.
- [x] Show current stage, owner, required date and append-only history without
  exposing engine terminology.
- [x] Let a Customer answer a clarification or withdraw when policy permits.

Exit: draft and submission journeys survive refresh and retry; list, detail and
mutation tests prove ownership and scope isolation.

## Phase 3: JIOC and request coordination

- [x] JIOC Routing Users claim and review submitted demand.
- [x] Record priority, completeness outcome, routing destination and reasons.
- [x] Automatically compare all submitted request fields across the authorised
  historical corpus, explain ranked matches and record duplicate, related
  request, existing output or not-relevant decisions.
- [x] Request clarification, close with reason or select any configured command.
- [x] Request Coordination Users return, hold, resume, close or select any direct Ops
  group with an append-only decision note.
- [x] Show time-stamped notes and activity to authorised participants only.

Exit: every decision is attributable and reconstructable; no search result escapes
the actor's scope; clarification and hold loops complete through real user tasks.

## Phase 4: Camunda routing and resilience

- [x] Validate and version the executable BPMN model using only user tasks and
  deterministic gateways based on human-supplied outcomes.
- [x] Deploy from an explicit, repeatable operator command.
- [x] Start and complete work through the V2 API behind a narrow workflow port.
- [x] Use stable business IDs, command idempotency, bounded retry and dead-letter
  visibility.
- [x] Reconcile pending commands and eventually consistent task search without
  inventing state.
- [x] Record process definition, instance, task and correlation identifiers.
- [x] Prove restart, timeout, duplicate command and engine-unavailable behaviour.

Exit: Camunda 8.9.14 moves a synthetic request through every human task and loop;
outages are visible and recoverable without duplicate requests or tasks.

## Phase 5: Ops routing and product delivery

- [x] Ops Routing Users select any direct delivery team or return with a reason.
- [x] Every configured team remains selectable and has its own seeded Manager and
  Analyst. A later staffing gap receives a genuine team task and waits visibly.
- [x] Team Managers accept, return, assign, reassign and monitor work within their
  team.
- [x] Team Analysts accept, return or query assigned work, add progress notes and
  submit a service product.
- [x] Provide role-scoped queues, ageing and workload views without an unrestricted
  global dashboard.
- [x] Enforce assignment, expected-state and optimistic-version checks on every
  action.

Exit: origin, ownership, workload and current state are accurate across queues;
stale, duplicate, cross-team and invalid-transition actions are denied.

## Phase 6: Manager check, QC, dissemination and feedback

- [x] Team Manager review and request changes or approve for QC.
- [x] QC User or QC Manager independently reviews, returns or approves; a
  distinct QC Manager explicitly disseminates to the originating Customer.
- [x] Enforce separation of duties and prevent authors from approving or releasing
  their own output.
- [x] Show disseminated content through an authenticated application-owned
  download only to its originating Customer.
- [x] Keep JIOC, command and Ops trackers read-only and remove them from the
  approval path after routing. Exact-route members may reopen the original
  submission, but not actions, clarification, feedback or product content.
- [x] Record Customer dissemination and permit one feedback response after completion.
- [x] Reconstruct the full request, decision, rework, approval and dissemination history.

Exit: happy path and rework path complete end to end with actor, reason, prior
state, next state and dissemination recipient evidence.

## Phase 7: Supporting administration and operations

- [x] Let local/test Platform Administrators create, activate or disable users,
  assign allowed roles and teams, and rename safe organisation display data.
- [x] Require re-authentication or elevated approval for sensitive admin changes.
- [x] Audit all admin changes with a tamper-evident metadata chain while keeping
  request content inaccessible.
- [x] Add retention jobs, backup procedures, restore verification and an operator
  runbook.
- [x] Define support hours, incident ownership, alert thresholds and safe
  diagnostic procedures.

Exit: administration cannot become a universal-content bypass; restore and
support exercises have named evidence and owners.

## Phase 8: Assurance, pilot and hand-off

- [x] Maintain 95 per cent line and branch coverage independently in backend and
  frontend application code.
- [x] Pass formatting, lint, type, build, migration, line and terminology gates.
- [ ] Pass dependency, secret, static security, container and licence checks.
- [ ] Pass the security matrix below with zero unresolved high or critical issues.
- [ ] Demonstrate WCAG 2.2 AA for keyboard, focus, names, errors, contrast and
  reduced motion in representative journeys.
- [x] Demonstrate p95 below two seconds for ordinary pages and API calls at agreed
  pilot load.
- [ ] Validate current Chrome, Edge and Firefox at the agreed support versions.
- [ ] Run Playwright pilot scenarios and visually inspect login, dashboard, form,
  request, queue, error, empty and narrow-screen states.
- [x] Run independent code-quality and defensive-security reviews.
- [ ] Complete user acceptance, operational rehearsal, backup/restore exercise and
  owner sign-off.

Exit: all Must requirements pass or have an owned, approved disposition; pilot
measures are captured; no data loss or unresolved severe security finding remains.

## Security verification matrix

| Scenario | Required result |
| --- | --- |
| Cross-role action | Denied and safely audited |
| Cross-scope list or detail | Record absent or denied without metadata leakage |
| Direct identifier manipulation | Denied at object policy |
| Workflow step skipped or repeated | Denied by expected state, task and version |
| Customer accesses another request or product | Denied |
| Analyst approves or disseminates own output | Denied |
| Non-child or skipped organisation selection | Denied |
| Unstaffed destination selected | Real waiting task; no OSG Team fallback |
| Tracker opens unreleased product content | Denied |
| Platform Administrator opens request content | Denied |
| Missing or reused CSRF token | Denied |
| Expired, disabled or replayed session | Denied |
| Duplicate submit or workflow command | One request and one task |
| Audit record altered | Hash-chain verification fails visibly |
| Sensitive content sent to logs | Test fails |
| Dependency unavailable | Safe pending/error state, no invented transition |
| Backup restored | Data and audit integrity verified |

Binary-file tests for type validation, malware quarantine, download disposition and
authorisation become mandatory only if files are approved in a later specification.

## Pilot scenarios

1. Save, resume, submit and track a complete request.
2. Request and answer clarification without losing the original revision.
3. Search authorised records and link a possible duplicate or related item.
4. Route through DIGOC → NCGI-A Ops → OSG Team, assign an Analyst and query work.
5. Complete a route through an alternative command, Ops group and staffed team;
   prove distinct Manager and Analyst candidate groups with no OSG Team fallback.
6. Record time-stamped progress notes and observe route-scoped, read-only
   routing trackers through the full lifecycle.
7. Submit the service product, complete Manager and QC rework, disseminate, download and
   give feedback without routing approval back up the hierarchy.
8. Attempt every cross-role, cross-scope, identifier and transition abuse case.
9. Reconstruct the history and recover from database or workflow interruption.

## Pilot measures

- proportion of submissions complete at first triage;
- median time from submission to triage and named ownership;
- proportion of records whose displayed owner and state match workflow truth;
- reduction in offline coordination and duplicate transcription;
- successful task completion rate and accessibility defects;
- Customer and staff satisfaction;
- workflow retry, reconciliation and operational incident counts;
- zero data loss and zero unresolved high or critical security findings.

Baselines and targets must be agreed before the pilot starts. Measures are
operational metadata and must not expose request content.

## Delivered: expansion programme (Expansions 0 to 8)

Status: Expansions 0 to 7 are complete and checked off below. Expansion 8's
technical, coverage, security, browser and recovery evidence is also complete;
only named product, security, operational and user-acceptance sign-off remains
open (its own final checklist item, and the aggregate acceptance gates
`DOD-50` to `DOD-54` in the
[Definition of Done matrix](assurance/DEFINITION_OF_DONE_MATRIX.md)).

This workstream extended the bounded workflow MVP without changing its
human-led routing principle. The Customer supplies structured demand. Routing
levels track and direct it. A delivery-team Analyst produces the service
product, the Team Manager checks it, a QC User or QC Manager performs quality
review, and a distinct QC Manager disseminates it. Work does not travel back
through JIOC, command or Ops for approval.

### Expansion 0: Rebaseline and authority

- [x] Define global and phase-specific completion gates.
- [x] Keep every configured unit staffed and document the complete synthetic
  account directory, including the independent configuration approver, in
  [Organisation and Routing](architecture/ORGANISATION_AND_ROUTING.md).
- [x] Accept the expansion product specification.
- [x] Accept management-grant, analytics, calendar and workflow-derived board
  decisions.
- [x] Update workflow, analytics and team-workspace threat models.
- [x] Seed exact management grants for JIOC, command, Ops and team managers.

Evidence: expansion specification, ADRs, threat models, organisation fixtures and
scope-policy tests.

### Expansion 1: Customer data quality and closure

- [x] Add private Customer draft create, resume, update and delete journeys.
- [x] Require every displayed business field at final submission in React and
  FastAPI, with accessible errors and deterministic focus.
- [x] Require structured evidence for routing, hold, return, rework and release
  decisions.
- [x] Put the authenticated released-product link directly in the Customer
  register as well as request detail.
- [x] Require one post-release service rating and feedback comment, with clear
  pending and submitted states.

Evidence: migration, validation contract tests, ownership and replay tests,
Customer Playwright journey and accessibility review.

### Expansion 2: Analyst-to-Customer clarification

- [x] Let the assigned Analyst request additional information from in-progress or
  rework states before product submission.
- [x] Store append-only clarification threads, including reason, response
  deadline, participants, messages and timestamps.
- [x] Show unanswered threads in the Customer `Needs your input` view and return
  answered work to the same delivery team and Analyst.
- [x] Show routing trackers only the metadata state `Awaiting Customer
  information`.
- [x] Version the BPMN definition and prove repeated clarification loops through
  live Camunda.

Evidence: BPMN contract, process-version record, database tests, scope-abuse tests,
React Analyst/Customer journeys and the live Camunda evidence ledger. The complete
browser journey remains part of Expansion 8 assurance.

### Expansion 3: Management grants and scoped analytics facts

- [x] Represent management authority as expiring grants over an exact
  organisation unit and optional descendants.
- [x] Give statistics, roster, calendar, board and capacity separate actions.
- [x] Add cycle-safe organisation closure data and bounded descendant queries.
- [x] Project idempotent request facts and stage intervals without business
  content or Customer identity.
- [x] Prove exact-unit, descendant, ancestor, sibling, revoked and expired cases.

Evidence: migration, management policy tests, analytics minimisation tests and
reconciliation evidence.

### Expansion 4: Scope-aware statistics workspaces

- [x] Provide JIOC managers with authorised JIOC and descendant statistics.
- [x] Provide DIGOC, SYGOC and MYGOC managers only their command and descendant
  statistics.
- [x] Provide NCGI-A Ops, Aurora Ops, Nimbus Ops and other Ops managers only their
  own group and direct-team statistics.
- [x] Provide Team Managers only their exact-team statistics and Platform
  Administrators selectable content-free aggregates from the configured root.
- [x] Authorise drill-down from each grant root to its descendants while denying
  every parent, sibling and unit belonging only to another grant.
- [x] Add role-specific operational, team, quality and administration overviews
  without merging personal work or Customer requests into statistics.
- [x] Show bounded traffic, WIP, age, due risk, throughput, stage duration,
  clarification, rework, feedback and child-unit comparisons.
- [x] Provide accessible table equivalents and suppress unsafe small feedback
  cohorts.

Evidence: the cross-branch API matrix and aggregate fixture oracle cover Platform,
JIOC, command, Ops and Team boundaries. The React dashboard provides grant-aware
navigation, bounded date and time-zone controls, freshness state, chart/table
parity and small-cohort suppression. The full gates pass at 474 backend tests
(98.75% line, 95.51% branch) and 161 frontend tests (99.37% line, 95.52%
branch). Performance and live-browser evidence are consolidated in Expansion 8.

### Expansion 5: Team workspace and roster lifecycle

- [x] Give every team an authorised Overview, Board, Calendar, People and Activity workspace.
- [x] Let an exact-team Manager add an existing active Analyst, end membership or
  schedule a transfer with a mandatory reason.
- [x] Keep global account creation, deactivation and role changes with Platform
  Administrators only.
- [x] Enforce one effective home team and require safe disposition of active work,
  packages, commitments and reservations before a move.
- [x] Preserve membership history and prevent sibling, ancestor and unrelated-team
  changes.
- [x] Make every People column keyboard-sortable, default Managers first and
  require current exact-unit Manager position as well as roster authority for
  every local membership operation.

Evidence: the membership timeline migration, scheduled one-winner tests,
authority matrix, active-request, package, commitment and reservation guards and
accessible Manager and Analyst journeys pass. A browser handover moved package
ownership and its workload count to the replacement Analyst before the original
membership action became available.

### Expansion 6: Canonical workforce calendar

- [x] Provide personal month, week and agenda views plus an authorised shared-team
  view.
- [x] Support all-day and timed activities, IANA time zones, daily and weekly
  recurrence, occurrence edits, future-series splits and cancellation.
- [x] Support private, availability-only and team-detail visibility.
- [x] Project each canonical event into personal and authorised exact-team views
  without copied absence records. Organisational ancestors receive scoped
  aggregate statistics rather than individual calendar records.
- [x] Let authorised Managers create team events and personal commitments, with
  acknowledgement or reasoned dispute by the subject.
- [x] Apply versioned preview and commit to calendar-backed capacity.
- [x] Use one accessible calendar-event modal opened by the Add event control or
  a selected calendar day.

Evidence: migration `0007_canonical_calendar` passed empty upgrade, drift,
downgrade to `0006`, re-upgrade and second drift. Recurrence, DST, privacy,
authority, optimistic-version, commitment, capacity and roster-disposition tests
pass. The final aggregate gates close at 513 backend tests (99.59% line, 97.48%
branch) and 183 frontend tests (99.41% line, 95.15% branch). The complete
PostgreSQL and Camunda browser matrix remains part of Expansion 8.

### Expansion 7: Workflow-derived Kanban and agile planning

- [x] Provide board and table views for awaiting assignment, ready, in progress,
  blocked, Manager review, quality review, rework, on hold and recently completed
  work.
- [x] Keep request movement derived from Camunda actions, never direct column
  mutation.
- [x] Add filters, saved views, WIP limits and keyset pagination.
- [x] Add versioned backlog work packages with ownership, contributors, estimate,
  remaining effort, due date, priority, dependencies, blockers, acceptance
  criteria and immutable activity.
- [x] Add calendar-backed capacity reservations, safe reassignment and optional
  time-boxed iterations.

Evidence: migration `0008_team_agile_planning`, workflow-projection and transition
tests, WIP and concurrency tests, package history, saved-view and keyset tests,
keyboard-accessible board actions and calendar capacity reconciliation. The real
React and FastAPI browser journey created and moved a package, reassigned it from
one Team Analyst to another, and verified the roster workload and removal guard
followed the new owner. Final aggregate coverage is 513 backend tests at 99.59%
line and 97.48% branch, and 183 frontend tests at 99.41% line and 95.15% branch.

### Expansion 8: Assurance and pilot

- [x] Rehearse empty and previous-schema migrations, backup and restore.
- [x] Pass backend and frontend 95 per cent line and branch coverage gates.
- [x] Pass formatting, lint, type, build, terminology, BPMN and OpenAPI checks.
- [x] Pass dependency, secret, static, container and licence checks with no
  unresolved high or critical finding.
- [x] Pass the complete permission, privacy, accessibility, browser, performance
  and recovery matrices.
- [x] Run Customer, Analyst, Manager, Quality and Release, statistics, roster,
  calendar and Kanban Playwright journeys against PostgreSQL and Camunda.
- [ ] Obtain product, security, operational and user-acceptance sign-off.

Evidence: the [Definition of Done matrix](assurance/DEFINITION_OF_DONE_MATRIX.md)
and signed [acceptance record](assurance/ACCEPTANCE_RECORD.md).

Evidence to date: migrations and a clean PostgreSQL restore pass. The complete
Customer, clarification, OSG Team delivery and alternative-team journeys pass against
PostgreSQL and Camunda 8.9.14. Current Chrome, Edge and Firefox render and operate
critical authenticated pages; named pages have zero axe violations and keyboard,
narrow-width and reduced-motion checks pass. Controlled database and Camunda
interruptions recover without loss or duplicate work. The agreed 250-user,
5,000-calendar-occurrence and 2,500-package fixture passed a two-minute warm-up
and ten-minute, 50-concurrent-user run at 945.29 ms p95, 1,114.85 ms p99 and
0.002 per cent errors. Bandit, dependency audits,
licences, digest-pinned source secret scanning and both rebuilt application
images pass at high and critical severity. Captured live logs were also checked
for known request, clarification, product, feedback and authentication values,
with no prohibited value found.

The reviewed Git baseline is committed and published to the explicitly selected
public remote with a fully passing hosted CI run. Named stakeholder sign-off
remains open.
These are not inferred from technical evidence.

## Delivered: expanded product capabilities

Status: implemented and running behind independent production-off feature
flags since 9 August 2026. This phase's own scope is code-complete; it is
extended and hardened by most of the dated milestone sections below (Guided
configuration, Operator orientation, Maintainability, Simplicity,
August security-remediation, Unified organisation workspace, Access
assistance, Explainable related-request matching, Action-oriented team
workspace, Role-aware action navigation, Personalised overview, Explicit
personal-calendar visibility, Plain-language request coordination, Separated
delivery-board, Request-tracking journey and Routing workspace monitoring). It
is not yet part of the accepted connected-environment MVP baseline.

This phase added role-specific personal workspaces, an auditable notification
centre, managed PDF, DOCX and PPTX dissemination or approved HTTPS product
links, effective-dated organisation and bounded workflow configuration,
team-planning enhancements and further scoped operational statistics.

This work is specified in
[Operational product capabilities](specs/operational-product-evolution.md) and its
completion state is tracked in the
[detailed capability gates](assurance/DEFINITION_OF_DONE_MATRIX.md#detailed-current-capability-gates),
where several `PE-DOD` rows (notification delivery, managed-file scanning,
organisation/workflow configuration and statistics evidence) remain `OPEN` or
`IN PROGRESS`. No phase is accepted until its own migrations, permission
matrix, security, accessibility, browser, recovery, performance and
named-acceptance evidence passes.

The local regression evidence recorded when this phase's first slice closed
was 880 backend tests at 98.84 per cent line and 95.19 per cent branch
coverage, plus 288 frontend tests at 99.49 per cent statements and 95.06 per
cent branches, with migrations 0012 to 0021 passing the repository's empty
SQLite upgrade, schema drift, downgrade and re-upgrade gates. That evidence is
long superseded: the current aggregate is 1,323 backend tests and migrations
through 0047, recorded in
[Current position](#current-position-15-august-2026) at the top of this plan.
Independent code-quality, workflow and security reviews at the time produced
findings that were addressed in the working tree. Fresh PostgreSQL migration
and runtime-denial evidence passed. One-winner activation, deployed Camunda
sibling routing, target scanner/object storage, full supported-browser
state-changing journeys, multi-store recovery and named acceptance gates
remained open at that point and are tracked to closure through the detailed
capability gates referenced above.

## Production readiness, intentionally separate

The local MVP is not a production deployment. Production remains blocked until:

- the identity provider, hosting model, regions and network boundaries are agreed;
- Camunda Self-Managed licensing and a compatible supported Helm release are
  confirmed;
- secrets management, encryption keys, certificates and private connectivity are
  provisioned;
- durable source-based authentication throttling is enforced at the trusted edge
  or through a shared product store;
- a distinct migration owner grants the runtime product role only the permissions
  it needs, audit UPDATE and DELETE are denied at database level, and scheduled
  integrity verification is evidenced;
- retention, deletion, information-handling and recipient rules are approved;
- staging penetration, dependency, container and recovery evidence passes;
- monitoring, alerting, incident response, support and rollback owners accept the
  release.

## Capabilities outside the implemented baseline

- production release of the implemented personal inboxes, notifications,
  managed-product files and versioned configuration remains governed by the
  product-evolution evidence and owner-acceptance gates;
- external messaging and external calendar synchronisation remain deferred until
  separate connector specifications and threat models are approved;
- automated classification, matching, prioritisation, routing or recommendations;
- predictive analytics, forecasting and automated capacity optimisation;
- unrestricted external-system integration, in-flight process migration and
  arbitrary dynamic form or workflow design.

## Definition of complete

A phase is complete only when code, migrations, tests, security evidence, user
documentation and operational notes agree. A manual walkthrough, passing unit tests or a
working Camunda path alone is not sufficient.

## Guided configuration and enterprise documentation milestone

Status: local implementation evidence ready on 7 August 2026; live and named
acceptance gates remain open.

- [x] Use current configuration, proposed changes, review and activation
  language in the administrator interface while retaining immutable revisions
  internally.
- [x] Refresh configuration history before navigating to newly created proposed
  changes so the selector and working record cannot disagree.
- [x] Add literal name/code/kind hierarchy search, ancestor context, accessible
  result feedback and filtered keyboard navigation.
- [x] Add a keyboard-operable selected-unit breadcrumb.
- [x] Filter create and move parents by effective time, routing state and exact
  hierarchy kind, excluding self and the unchanged current parent.
- [x] Reject provisional same-effective-time move edges so an invalid
  zero-length interval cannot be produced.
- [x] Canonicalise reminder schedules and report staffing preview impact only
  when the proposal introduces or raises the shortfall.
- [x] Add the complex configuration and human-routing user stories, ADR 0018,
  role/permission matrix, threat controls, audit catalogue, operations runbook,
  traceability update and enterprise gap register.
- [x] Add focused frontend and backend regression coverage.
- [x] Pass the full frontend/backend coverage, static, build, terminology,
  OpenAPI, BPMN and line-limit gates on the final working tree.
- [x] Bind approval and activation to a canonical snapshot digest, seal current
  and historical components and approved workflow identity in PostgreSQL, and
  fail new pins/readiness closed on evidence mismatch.
- [x] Preview restoration after temporary scheduled changes, remove later
  schedule entries on retirement, and compare semantically unordered template
  values canonically.
- [x] Prove an empty PostgreSQL 17 migration and first-start baseline at 0018,
  plus runtime-role denials for sealed component reassignment and approved
  workflow identity mutation.
- [x] Add requirement traceability, the current documentation home, continuity
  framework, detailed configuration permission matrix and one unsigned
  acceptance record.
- [ ] Record live browser, narrow-width, 200% zoom, three-browser, large-tree
  performance, forged-parent, PostgreSQL concurrency and Camunda route evidence.
- [ ] Obtain named product, security, operational and representative-user
  acceptance. Until then, this remains a non-production local release candidate.

## Operator orientation and factual timing milestone

Status: local implementation and focused browser evidence ready on 8 August
2026; full gates and representative acceptance remain required.

- [x] Return the selected request-pinned routing path with only the authorised
  immediate-child destination options.
- [x] Add literal, case-insensitive name/code filtering, visible result counts
  and a selected-route summary without ranking or recommendation.
- [x] Add a richer account menu with account ID, role, scope, session state and
  sign-out, while keeping one correct active primary-navigation item.
- [x] Differentiate active, hover and keyboard-focus states and strengthen
  readable workflow status styling.
- [x] Show factual service age, current-owner or task waiting time and required
  date proximity without changing workflow state or priority.
- [x] Add backend, frontend, accessibility and timing-boundary regression tests.
- [x] Inspect desktop and 640-pixel layouts in the local Chromium browser,
  including one-current-link behaviour, Escape close, route close, focus outline
  and popover containment.
- [x] Complete the full repository gates and target PostgreSQL/Camunda recovery
  rehearsal, including a fresh-stack alternative route and breadcrumb payload.
- [ ] Obtain representative JIOC, Command, Ops, Customer and accessibility
  acceptance.

## Maintainability and portable evaluation milestone

Status: local implementation and documentation evidence ready on 8 August 2026;
connected production remains blocked by the enterprise gap register.

- [x] Add recurring frontend and backend dead-code gates, including a
  production-only frontend export check.
- [x] Keep production services, database helpers and product-availability paths
  free of confirmed dead code while retaining migration, decision and assurance
  history.
- [x] Batch immutable request-policy projection, bound broad query parameter
  sets and avoid mutable organisation lookups for fully pinned requests.
- [x] Validate completion at both authoritative transaction boundaries without
  redundant intermediate checks.
- [x] Avoid eager hidden completed-product panels, retry all request/draft and
  team-planning dependencies coherently, and reduce calendar/date allocation.
- [x] Correct local workflow attestation to run inside Compose and test its
  argument, failure and working-directory behaviour.
- [x] Forward documented database-pool, session, elevation and process settings
  through Compose.
- [x] Require asyncpg-compatible `ssl=verify-full` in production and prove the
  resulting SQLAlchemy connect arguments.
- [x] Require sealed runtime configuration readiness even when configuration
  administration is disabled.
- [x] Add a current architecture authority, documentation map, configuration
  reference, release runbook and explicit production gates.
- [x] Add stepwise Windows, macOS and Linux Docker/source guides and private
  synthetic AWS, Google Cloud and Azure VM guides.
- [x] Document the portable Kubernetes production target without claiming that
  absent IaC, identity or product-runtime integrations exist.
- [x] Add broken-link and long-form documentation-duplication gates, retaining
  historical evidence with explicit dated labels.
- [x] Add keyset pagination/index evidence, route-level web code splitting and
  target-scale performance proof.
- [ ] Batch expanded product-release metadata where a later measured release
  workload proves that another projection is required.
- [ ] Implement and validate OIDC, secure Camunda client auth, cloud product
  storage/scanning, IaC and joined multi-store recovery before connected use.

## Simplicity and runtime-efficiency deep dive

Status: runtime hardening and target-scale evidence completed on 8 August 2026.
Atomic concurrent Board WIP enforcement remains explicitly excluded at the
product owner's direction.

- [x] Lazy-load every top-level page and the heavy Team workspace views while
  preserving the existing capability and role gates.
- [x] Enforce Vite-manifest entry budgets after every production web build.
- [x] Stop non-team roles loading team-workspace navigation data and stop the
  notification-count poll competing with the active Notifications register.
- [x] Batch notification eligibility, membership, preference, existing-row and
  state-target reads, flush recipients once and refresh checkpoint counts once
  per projection batch.
- [x] Make unchanged configuration restoration stable for unit versions and
  organisation-closure rows.
- [x] Keep routing-filter selection, calendar occurrence editor identity and
  local browser date values coherent.
- [x] Keep unused planning ports, repository methods and in-memory test adapters
  out of the production package.
- [x] Move scheduled membership compatibility projection out of every request,
  with a due-transition index/checkpoint, worker health and fail-closed
  authorisation tests.
- [x] Redesign workflow-command and product upload/release processing so leases
  bracket external Camunda, object-store and scanner calls without holding
  database locks or transactions.
- [x] Release database sessions before product response streaming and prove
  cancellation and access-audit behaviour under a slow stream.
- [x] Add keyset pagination and proven PostgreSQL indexes to work, request,
  draft, tracking, administrator and older-history feeds.
- [x] Move Board filtering and pagination into PostgreSQL.
- [ ] Enforce Board WIP limits atomically under concurrent moves. This remains
  explicitly excluded from the current milestone at product-owner direction.
- [x] Separate maintenance workloads from API replica count, isolate failure
  domains and introduce measured idle backoff and fairness budgets.
- [x] Split the Work Package form core, API clients and dense React orchestration
  modules by domain before adding an enforceable source-line-length gate.
- [x] Run PostgreSQL statement-count and `EXPLAIN (ANALYSE, BUFFERS)` evidence,
  multi-replica contention tests and browser traces at the agreed target scale.

## August security-remediation milestone

Status: implementation complete on 9 August 2026; final automated evidence is
recorded. MVP identity replacement and GitHub branch protection are excluded by
product-owner direction.

- [x] Run PostgreSQL 17.10 as non-root without `gosu`.
- [x] Keep Python build tooling out of the API runtime, run Nginx as non-root on
  port 8080 and keep unused vulnerable packages out of the Camunda image.
- [x] Separate ClamAV update egress from the internal-only non-root daemon and
  fail health from signed definition age or loaded/on-disk version mismatch.
- [x] Add short-transaction atomic PostgreSQL global/source login budgets, safe
  proxy handling, one-way source identifiers, cancellation durability, generic
  throttling responses and bounded Argon2 concurrency.
- [x] Disable production API documentation surfaces and add response isolation
  plus no-store controls.
- [x] Build and scan API, web, PostgreSQL, Camunda and ClamAV images in CI and
  produce a CycloneDX SBOM for each.
- [x] Add scheduled npm, Python, GitHub Actions and Docker dependency updates.
- [x] Permit only one exact hashed, expiring synthetic-fixture Git-history
  exception, which can never cover a verified finding.
- [x] Add the security specification, ADR 0021, threat-model changes, private
  reporting policy and deployment guidance.
- [x] Attach final current-candidate test, scan, image and fresh-readiness
  results to the security evidence record.
- [ ] Obtain security-owner acceptance and any independent penetration-test
  evidence required by the target environment.

## Unified organisation workspace milestone

Status: implemented locally on 9 August 2026. Final repository and live-runtime
evidence is recorded in the assurance documents. Connected-environment rollout
remains subject to the enterprise gap register.

- [x] Make effective-dated Manager and Member membership authoritative for every
  JIOC, command, Ops and delivery-team workspace.
- [x] Seed one named Manager and Member in every routing unit, preserve all
  existing identities and extend the sequential local directory to `admin99`.
- [x] Give every current workspace member calendar self-service for leave,
  courses, training, duty, appointments and availability.
- [x] Use one date-aware Add event modal from both the calendar toolbar and day
  cells, preserving errors and returning focus after close.
- [x] Limit unit events to exact-unit Managers and request-linked commitments to
  delivery-team Managers, current Analysts and work owned by that exact team.
- [x] Allocate one accountable Lead and up to ten additional Analysts, retaining
  effective history, mandatory evidence and optimistic version checks.
- [x] Keep the Lead as the accountable Camunda assignee while granting every
  currently assigned Analyst the same production controls.
- [x] Provide routing workspaces with Overview, Work queue, Calendar, People,
  Statistics and Activity without introducing Manager approval.
- [x] Provide delivery workspaces with Overview, Work queue, Board, Calendar,
  People, Statistics and Activity.
- [x] Add bounded description, assignment, risk, blocker, decision and HTTPS-link
  records with immutable create and resolve events.
- [x] Keep statistics inside each explicit unit-and-descendant grant, excluding
  parent and sibling branches.
- [x] Add migrations 0024 to 0027, update restore expectations, threat modelling,
  architecture, user directory and operational documentation.
- [x] Add positive, negative, cross-unit, effective-date, assignment-history,
  calendar, collaboration, accessibility and workflow regression tests.
- [x] Prove Manager-first and seven-column roster sorting plus a fail-closed
  deliberately misconfigured Member roster grant.
- [x] Pass 922 backend tests at 98.26 per cent coverage and 321 frontend tests
  at 99.40 per cent line and 95.03 per cent branch coverage.
- [x] Pass repository policy, formatting, lint, type, dead-code, line-limit,
  documentation, licence, dependency-audit, Bandit, build and bundle gates.
- [x] Rebuild the local Compose application, confirm all services healthy,
  exercise the Camunda route contract and inspect JIOC and OSG Team workspaces in
  Chromium with no unexpected authenticated-page console error.
- [x] Upgrade a disposable PostgreSQL database from empty to revision 0027,
  downgrade to 0023, re-upgrade and confirm no model drift.
- [ ] Obtain representative user acceptance from JIOC, command, Ops, OSG Team and QC
  users before connected-environment rollout.

## Access assistance and global classification milestone

Status: implemented and assured locally on 10 August 2026. Connected-environment
rollout remains subject to the enterprise gap register.

- [x] Add a secondary forgotten-password journey to the existing sign-in panel,
  using mandatory, validated work email and a deliberately non-disclosing result.
- [x] Notify every active Platform Administrator when an active account matches,
  while suppressing duplicates and applying shared source and global limits.
- [x] Persist no submitted email in assistance-attempt records and retain only a
  one-way source key, optional internal account identifier and timestamps.
- [x] Add unique normalised account email to the governed identity directory,
  Customer profile and Administrator create/edit surfaces.
- [x] Add a versioned, audited PostgreSQL singleton for `OFFICIAL`,
  `OFFICIAL-SENSITIVE`, `SECRET` and `TOP-SECRET`, defaulting to `OFFICIAL`.
- [x] Require Platform Administrator role, CSRF, fresh step-up and expected
  version for global classification changes.
- [x] Add a 22-pixel persistent, accessible classification strip above every
  anonymous and authenticated page, with restrained green, blue and red states.
- [x] Add the feature specification, ADR 0026, architecture, permission and
  threat-model changes without duplicating operational procedures.
- [x] Prove empty-to-0028 PostgreSQL upgrade, downgrade to 0027, re-upgrade and
  drift-free metadata, correcting the UUID bind defect exposed by PostgreSQL.
- [x] Pass 926 backend tests at 98.84 per cent line and 95.08 per cent branch
  coverage, plus 326 frontend tests at 99.41 per cent line and 95.01 per cent
  branch coverage.
- [x] Complete full repository gates and live Chromium visual/accessibility
  evidence.

## Explainable related-request matching milestone

- [x] Keep the JIOC progress API and interface free from uncontrolled category
  input while retaining safe compatibility with stored records.
- [x] Create one all-field search projection atomically with every submitted
  request and backfill the existing corpus through migration 0029.
- [x] Add indexed PostgreSQL full-text, trigram and pgvector retrieval without a
  second search datastore.
- [x] Generate embeddings asynchronously with a fenced worker and an offline,
  revision and checksum-verified FastEmbed model cache.
- [x] Reapply claimed-task and route-membership authorisation to source,
  candidates, explanations and recorded decisions.
- [x] Show automatic top matches, match strength, contributing methods, bounded
  field evidence and optional all-field search in the JIOC workspace.
- [x] Keep matching advisory and store possible duplicate, related request,
  existing released product and not-relevant human decisions without changing
  workflow position.
- [x] Prove the live PostgreSQL extensions, indexes, ten-record backfill and
  complete semantic projection, plus hybrid API and browser behaviour.
- [x] Complete the disposable PostgreSQL 0029 downgrade/re-upgrade and drift
  rehearsal.
- [ ] Complete a coordinated current-candidate backup/restore before release
  acceptance.

## Action-oriented team workspace milestone

Status: implemented and assured locally on 10 August 2026. Representative-user
acceptance remains required.

- [x] Present linked overdue, assignment, clarification, review, capacity,
  calendar, people, handover and activity signals on the delivery overview.
- [x] Give routing units a separately designed, unit-scoped decision home without
  delivery allocation or a Manager approval stage.
- [x] Return complete filtered Board column aggregates independently of the
  cursor-bounded item page.
- [x] Focus the default Kanban on active delivery, with expandable downstream,
  exception and terminal groups plus an equivalent table presentation.
- [x] Add built-in and saved views, WIP signals, compact filters, a focused work-
  package drawer and an accessible request/package inspector.
- [x] Keep request movement behind named Camunda workflow actions and package
  movement behind explicit, reasoned, versioned commands.
- [x] Surface customer clarification, Lead review, blockers, dependency warnings,
  capacity reservations, calendar availability, iteration progress and handover
  context at the point of work.
- [x] Add up to twelve normalised, unique, self-declared operational skill labels
  to Profile and the authorised exact-team people view without scoring or
  automated assignment.
- [x] Scope every routing queue read to the selected organisation unit.
- [x] Complete full backend and frontend coverage, policy, migration and live-
  browser assurance for the current candidate. The final evidence is 940
  backend tests at 98.88 per cent statement and 95.06 per cent branch coverage,
  plus 337 frontend tests at 99.46 per cent line and 95.03 per cent branch
  coverage.
- [ ] Obtain representative acceptance from a routing Manager, routing Member,
  delivery Team Manager and delivery Analyst.

## Role-aware action navigation milestone

Status: implemented and assured locally on 10 August 2026. Representative-user
acceptance remains required.

- [x] Use role-specific action, queue and workspace labels, including `My
  assigned actions`, `JIOC routing queue` and `JIOC workspace`.
- [x] Project every operational action to its role-owned queue with an exact,
  server-authorised `requestId` selector instead of a Customer-only detail URL.
- [x] Keep shared, unclaimed work visible to the authorised unit while making a
  claimed action personal to the assignee and removing it from peer registers.
- [x] Refuse to substitute another queue item when a linked action was completed,
  claimed by somebody else or left the actor's scope.
- [x] Backfill existing active actions through migration 0031, preserving the
  safer personal audience on downgrade and repairing the reported Russian Troop
  Movements card.
- [x] Add positive role-route, exact-selection, claim-isolation, empty-state and
  legacy-projection regression coverage.
- [x] Record the access-control analysis in the workflow threat model and the
  projection, selection and navigation boundaries in system architecture.
- [x] Exercise admin4 in the local browser and prove that Open selects Russian
  Troop Movements in the JIOC routing queue rather than redirecting to Overview.
- [x] Pass 951 backend tests at 98.88 per cent statement and 95.06 per cent
  branch coverage, plus 338 frontend tests at 99.46 per cent line and 95.00 per
  cent branch coverage.
- [x] Pass formatting, Ruff, MyPy, Bandit, ESLint, TypeScript, dead-code,
  line-limit, documentation, licence, OpenAPI, Dependabot, secret-scan contract,
  dependency-audit, production-build and PostgreSQL schema-drift gates.
- [ ] Obtain acceptance from representative JIOC, command, Ops, delivery and QC
  users for the final labels and linked-action recovery message.

## Compact previous-request evidence milestone

Status: implemented and assured locally on 10 August 2026. Representative JIOC
acceptance remains required.

- [x] Keep automatic comparison running without automatically exposing a long
  list of advisory results in the routing form.
- [x] Show a compact collapsed summary that distinguishes strong matches from
  lower-confidence suggestions and does not imply a weak score is a match.
- [x] Reveal manual history search, match evidence and human-decision controls
  through a labelled, keyboard-operable disclosure.
- [x] Bound expanded results to a keyboard-focusable scrolling region of at most
  330 px or 42 per cent of viewport height.
- [x] Retain existing request-scope authorisation and advisory-only routing
  semantics without changing the API or workflow.
- [x] Pass the complete 339-test frontend suite at 99.46 per cent line and 95.02
  per cent branch coverage, plus TypeScript, ESLint and line-limit checks.
- [ ] Obtain representative JIOC acceptance for the summary wording and expanded
  result height at normal operational display sizes.

## Workspace-authority identity milestone

Status: implemented and assured locally on 10 August 2026.

- [x] Preserve `JIOC Routing User` as the representative workflow role while
  displaying the independent, permission-bearing Manager or Member position.
- [x] Combine role and position in the compact account identity and name each
  organisation-position pair explicitly in the account details and profile.
- [x] Keep the effective server-side membership and grant as the sole
  authorisation source; presentation remains explanatory only.
- [x] Cover Manager, Member, mixed, loading, unavailable and no-position states.
- [x] Pass 367 frontend tests at 99.51 per cent line and 95.03 per cent branch
  coverage, all repository gates and the production bundle budget.

## Personalised overview and primary-navigation milestone

Status: implemented and assured locally on 10 August 2026. Representative-user
acceptance remains required.

- [x] Greet routing, quality and administration users by first name.
- [x] Separate personal assigned-action measures from explicitly named aggregate
  organisation workload and explain that aggregate values are not personal.
- [x] Keep direct-child organisation drill-down on Operational statistics and
  use explanatory staff Home tiles for every other authorised
  primary-navigation destination.
- [x] Order navigation deterministically as Home, assigned actions, role queue,
  named workspace, role tools, request tracking, operational statistics and
  organisation directory, omitting destinations the account cannot use.
- [x] Rename ambiguous sidebar destinations without changing routes or
  authorisation.
- [x] Pass 368 frontend tests at 99.52 per cent line and 95.06 per cent branch
  coverage, including accessible tile navigation, capability-derived links,
  zero states and reduced-motion styling.
- [ ] Obtain representative JIOC, command, Ops, QC and Administrator acceptance
  for the final wording and information hierarchy.

## Explicit personal-calendar visibility milestone

Status: implemented and assured locally on 10 August 2026. Representative-user
acceptance remains required.

- [x] Default new personal activity to exact-unit detail from My calendar and
  the shared organisation calendar.
- [x] Use one unchecked, accessible `Private appointment` choice with immediate
  plain-language audience guidance.
- [x] Keep personal sharing context separate from Manager-only unit-event and
  ticket-commitment authority.
- [x] Reject new availability-only personal writes at the FastAPI use-case
  boundary while retaining existing canonical records and projection redaction.
- [x] Update the feature specification, calendar ADR, workspace specification,
  threat model and development record.
- [x] Pass 953 backend tests at 98.87 per cent statement and 95.00 per cent
  branch coverage, plus 368 frontend tests at 99.52 per cent line and 95.03 per
  cent branch coverage, including the unit-name failure path.
- [ ] Obtain representative routing and delivery-user acceptance for the final
  checkbox wording and default audience.

## Plain-language request coordination milestone

Status: implemented and assured locally on 10 August 2026. Representative-user
acceptance remains required.

- [x] Label the coordination queue `Incoming requests` and explain the required
  human action in plain language.
- [x] Use the current coordination wording consistently across the UI, workflow
  task metadata, smoke contracts and current reference documentation.
- [x] Resolve shared action ownership from the pinned organisation route and
  distinguish `<unit> · Awaiting owner` from personal assignment.
- [x] Preserve stable internal role, status, action and BPMN element identifiers.
- [x] Migrate existing presentation values without deleting or rebuilding local
  request data.
- [x] Pass 953 backend tests plus the defensive ownership regression at 98.87
  per cent line and 95.02 per cent branch coverage, 369 frontend tests at 99.52
  per cent line and 95.06 per cent branch coverage, and all repository checks.
- [ ] Obtain representative DIGOC, SYGOC and MYGOC acceptance for the final
  queue and ownership wording.

## Separated delivery-board milestone

Status: implemented and assured locally on 13 August 2026. Representative-user
acceptance remains required.

- [x] Keep the Service request board always visible and driven only by named
  workflow actions.
- [x] Explain each service-request lane in small plain-language text beneath its
  title.
- [x] Present internal work packages in a separately labelled Kanban that is
  collapsed by default and lazy-loaded when opened.
- [x] Put a prominent `Create internal card` action inside the expanded Kanban,
  fix Analyst-created cards to the current Analyst, and retain owner or
  contributor checks for Analyst moves.
- [x] Preserve reasoned, audited manual moves for work packages without allowing
  service-request cards to be dragged.
- [x] Keep filtering, saved views, aggregate counts, independent paging, table
  mode, WIP settings and retry states operational across the split boards.
- [x] Pass all 394 frontend tests at 99.41 per cent line and 95.01 per cent
  branch coverage, plus the production build, ESLint, line-limit, documentation
  and terminology checks.
- [ ] Obtain representative Team Manager and Analyst acceptance for the board
  separation, collapsed default and lane wording.

## Request-tracking journey milestone

Status: implemented and assured locally on 13 August 2026. Representative-user
acceptance remains required.

- [x] Lead each tracked request with its current stage, current owner and next
  stage rather than requiring users to interpret two equal-weight timelines.
- [x] Present the selected organisation route as compact travel history with
  passed, current and selected-next states.
- [x] Begin the selected route with the Customer submission and finish it with
  a larger, visually dominant point for the current owner.
- [x] Name the signed-in viewer and mark `Your unit` only for exact route-unit
  identifiers in their authenticated session.
- [x] Give all five delivery stages a plain-language meaning and an explicit
  `Complete`, `Now` or `Next` label, with the current stage exposed through
  `aria-current="step"`.
- [x] Use a vertical route and delivery journey on narrow screens without
  horizontal scrolling, and respect reduced-motion preferences.
- [x] Preserve exact-route visibility and the existing read-only tracking
  boundary without adding workflow actions or new backend data.
- [x] Verify desktop and 390-pixel browser layouts with a clean console, pass
  all 395 frontend tests, and pass the build, bundle-budget and repository
  quality gates.
- [ ] Obtain representative JIOC, DIGOC and NCGI-A Ops acceptance for the new
  tracking hierarchy and stage wording.

## Routing workspace monitoring and Customer acceptance milestone

Status: implemented and assured locally on 13 August 2026. Representative-user
acceptance remains required.

- [x] Keep exact-unit routing actions in the dominant `Needs routing action`
  queue without granting authority through passive monitoring.
- [x] Add separate `Active requests routed onwards` and `Completed requests`
  registers to every routing workspace, both collapsed by default.
- [x] Show reference, title, status, current owner, required date, age and a
  read-only history link for monitored requests.
- [x] Keep disseminated managed products active for routing oversight until the
  originating Customer explicitly accepts them.
- [x] Store idempotent acceptance on the exact dissemination and append one
  attributable, hash-linked `PRODUCT_ACCEPTED` event.
- [x] Preserve approved external HTTPS links as valid product-only artefacts
  behind QC attestation, authenticated redirect, allow-list, expiry and
  withdrawal controls.
- [x] Verify desktop and 390-pixel browser layouts with a clean console, pass
  all 399 frontend tests and all 1,022 API tests, and pass the repository quality
  gates at or above 95 per cent line and branch coverage.
- [ ] Obtain representative routing-unit and Customer acceptance for the new
  separation and explicit acceptance wording.

## Deterministic post-login landing fix

Status: implemented and browser-verified locally on 13 August 2026.

- [x] Ignore the protected route that caused an anonymous user to reach sign-in.
- [x] Send every internal role to `/overview` after successful sign-in.
- [x] Send Customers to `/requests` after successful sign-in.
- [x] Preserve intentional deep links for sessions that are already authenticated.
- [x] Cover staff and Customer return-route regressions and verify both in the
  real local browser with a clean authenticated console.

## Live QA readiness and route assurance

Status: implemented and live-verified on 14 August 2026.

- [x] Recover the rebuilt QA stack from configuration-unavailable to full
  `/ready` without weakening the fail-closed configuration boundary.
- [x] Deploy and attest the exact approved BPMN over the isolated Compose
  workflow network without requiring host Camunda exposure.
- [x] Reuse one exact active process on restart and refuse conflicts or an
  existing unattested deployment without mutating workflow state.
- [x] Exercise the primary JIOC, DIGOC, NCGI-A Ops, OSG Team, Ben Doak, Manager,
  QC and Customer-download route through the real API, database and Camunda.
- [x] Exercise the configured SYGOC, Nimbus Ops and Beacon Team alternative
  through the same real application boundary.
- [x] Render John McGinn's full profile in the rebuilt UI without the historical
  application crash.
- [x] Give routing summaries and paginated work queues distinct query-cache
  identities, with an Overview-to-Queue regression test for populated units.

## Workflow runtime reliability remediation

Status: implemented and live-verified on 14 August 2026.

- [x] Prevent the maintenance worker from racing the originating API call for a
  newly committed human-workflow command while retaining five-second crash
  recovery.
- [x] Reconcile bounded competing leases from durable `SENT`, `FAILED`, pending
  and processing states without duplicating a Camunda effect.
- [x] Remove actor-row lock cycles between workflow or request-detail
  authorisation and notification recipient projection; bound residual command
  deadlocks to one idempotent retry.
- [x] Default maintained journey, load and seed tooling to the hardened
  port-5173 proxy-only topology.
- [x] Return nullable optional managed-product lookups for authorised legacy
  requests while concealing unknown and cross-Customer identifiers.
- [x] Emit content-minimised correlated diagnostics for unexpected API failures
  without request content, URLs, exception messages or credentials.
- [x] Complete seven consecutive rebuilt-stack journeys across both configured
  organisational routes with verified Customer downloads and no 5xx or deadlock
  log entries.
- [x] Verify a clean authenticated completed-request browser view with zero
  console errors or warnings and only successful application API responses.
- [x] Pass all 1,168 backend tests (10 skipped), all 424 frontend tests, backend
  coverage of 98.68 per cent line and 95.05 per cent branch, frontend coverage
  of 99.45 per cent line and 95.02 per cent branch, and the complete repository
  static, documentation, security-oriented and contract checks.

## SOLID, readability and maintainability programme

Status: implementation and runtime verification complete on 14 August 2026.

- [x] Add executable dependency, cycle, protocol-width, source-headroom,
  protected-query-key and frontend-complexity ratchets.
- [x] Reduce service-to-infrastructure, router-to-persistence,
  repository-to-service and backend import-cycle debt to zero.
- [x] Split broad product, conversation, work, configuration, board, calendar,
  administration and workspace capabilities behind focused ports and explicit
  composition modules.
- [x] Decompose frontend authentication, context, conversation, upload, queue
  and feature orchestration into focused controllers, hooks and renderers.
- [x] Reduce all maintained source below 330 lines and all production frontend
  functions to complexity 12 and nesting depth four.
- [x] Enforce canonical Prettier and Ruff formatting without lowering coverage,
  security or file-size gates.
- [x] Add a mandatory PostgreSQL 0043 to 0047 populated round trip and a
  Chromium journey from Customer submission through routing, OSG Team, QC, release,
  Customer retrieval and acceptance.
- [x] Pass the root quality gate, strict MyPy across 440 modules, Ruff, Bandit,
  1,318 backend tests at 98.73 per cent line and 95.00 per cent branch coverage,
  the production web build and 490 frontend tests at 98.8 per cent line and
  95.04 per cent branch coverage.
- [x] Capture the mandatory PostgreSQL and complete browser results against the
  immutable candidate. PostgreSQL passed populated upgrade, downgrade,
  re-upgrade, empty upgrade and metadata-drift checks. Chromium passed the
  complete Customer-to-acceptance route with context, conversation, managed
  package, review and separation-of-duty assertions.
