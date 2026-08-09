# Specification, decision and threat traceability

Recorded on 7 August 2026 and updated on 8 August 2026. Each implemented capability is mapped to its accepted
Markdown specification, expensive-to-reverse decision record and current threat
model. Shared foundation records apply where a feature uses an existing boundary
rather than creating a new architectural decision.

| Capability | Specification | ADR | Threat model |
| --- | --- | --- | --- |
| Customer form, drafts, tracking, release and feedback | `service-request-mvp.md` | 0001, 0002, 0003 | `service-request-workflow.md` |
| Human-led Camunda workflow | `service-request-mvp.md` | 0001, 0003 | `service-request-workflow.md` |
| Organisation tree and selectable routing | `service-request-mvp.md` | 0004 | `service-request-workflow.md` |
| Analyst clarification loop | `service-operations-expansion.md` | 0010 | `service-request-workflow.md` |
| Scoped statistics | `service-operations-expansion.md` | 0006, 0007 | `management-and-analytics.md` |
| Team roster lifecycle | `service-operations-expansion.md` | 0006, 0011 | `team-workspaces-and-calendars.md` |
| Shared and personal calendars | `service-operations-expansion.md` | 0006, 0008 | `team-workspaces-and-calendars.md` |
| Workflow board and agile planning | `service-operations-expansion.md` | 0006, 0009 | `team-workspaces-and-calendars.md` |
| Manual related records | `manual-related-records.md` | 0012 | `service-request-workflow.md` |
| Platform administration | `platform-administration-mvp.md` | 0005, 0013 | `platform-administration.md` |
| Retention, telemetry, backup and recovery | `operational-readiness.md` | 0014 | `operations-and-recovery.md` |
| Action and notification workspace | `operational-product-evolution.md` | 0015 | `service-request-workflow.md` |
| Managed product files and external links | `operational-product-evolution.md` | 0016 | `service-request-workflow.md` |
| Effective-dated organisation configuration | `operational-product-evolution.md` | 0017 | `platform-administration.md` |
| Guided configuration and routing experience | `configuration-administration-usability.md` | 0018 | `platform-administration.md`, `service-request-workflow.md` |
| Operator shell orientation and factual service timing | `operator-orientation-and-service-timing.md` | Existing shell and human-routing boundaries | `service-request-workflow.md` |
| Maintainability, dead-code control and portable evaluation | `maintainability-and-portable-evaluation.md` | 0019 | `operations-and-recovery.md` |
| Fenced maintenance, external-I/O phases and bounded operational feeds | `runtime-scaling-and-worker-hardening.md` | 0020 | `operations-and-recovery.md`, `service-request-workflow.md` |

All referenced records exist in `docs/specs`, `docs/adr` and
`docs/threat-model`. The Product Evolution Definition of Done matrix, master
implementation plan and enterprise gap register are the current aggregate
authorities for evidence, delivery status and human acceptance.

## Configuration and routing requirement trace

`Implemented` means code and automated evidence exist in the local candidate. It
does not mean enterprise or user acceptance. `Specified` means deliberately not
claimed by this milestone.

| Requirement | Principal permission/control | Automated evidence | Status |
|---|---|---|---|
| CAU-01 find units by name, code or kind | Platform Administrator read; bounded authorised response only | `configuration-components.test.tsx`, `configuration-flow.test.tsx` | Implemented |
| CAU-02 confirm context with breadcrumb | Platform Administrator read; stable codes remain visible | `configuration-components.test.tsx` | Implemented |
| CAU-03 create under a valid parent | Step-up mutation; backend exact-kind and effective-parent validation | configuration API, lifecycle and component tests | Implemented |
| CAU-04 move without cycle or invalid interval | Step-up mutation; complete snapshot and closure validation | lifecycle, projection and PostgreSQL permission tests | Implemented |
| CAU-05 use current/proposed operator language | Platform Administrator only; lifecycle names remain internal | component, flow and repository terminology gates | Implemented |
| CAU-06 independent review | Different actor, fresh step-up, exact revision and canonical digest | lifecycle, API, digest and PostgreSQL guard tests | Implemented |
| CAU-07 preserve in-flight work | Submission pins immutable configuration and process identity | pinning, workflow and configuration API tests | Implemented |
| CAU-08 fail safely and recover without rewrite | Optimistic revision, one-winner activation, fail-closed readiness, successor recovery | lifecycle mutability, readiness, restore and PostgreSQL guard tests | Implemented, live recovery acceptance open |
| HRU-01 direct-child human routing | Exact candidate group, claimed task, server-loaded children | routing, hierarchy and BPMN contract tests | Implemented |
| HRU-02 routing-stage path confirmation | Routing user, authorised current path only | routing repository, API and component tests | Implemented, representative acceptance open |
| HRU-03 routing destination search | Routing user, direct authorised children only | literal-filter component, API scope and accessibility tests | Implemented, representative acceptance open |
| HRU-04 explicit unstaffed selection | Human choice retained; no OSG fallback | routing, staffing and workflow tests | Implemented |
| HRU-05 stale destination rejection | Request pin, parent, stage and expected revision checked server-side | routing and configuration pin tests | Implemented |
| HRU-06 competing claim | Exact candidate group and active task; one winner | workflow concurrency and API tests | Implemented |
| HRU-07 stored clarification loop | Customer ownership or named human assignment | clarification API, workflow and browser evidence | Implemented |
| HRU-08 tracking without approval | Selected path scope; no downstream approval for ancestors | tracking, statistics and negative authorisation tests | Implemented |

Threat ownership for CAU requirements is `platform-administration.md`; HRU
requirements use `service-request-workflow.md`. Exact action boundaries are in
`docs/reference/ROLE_PERMISSION_MATRIX.md`. Acceptance gates PE-DOD-40 to 45,
60 to 68 and 70 to 74 remain authoritative for unresolved live and human
evidence.
