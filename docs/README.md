# ISTARI Service documentation home

Status: current documentation map
Last reviewed: 11 August 2026

This is the starting point for product, delivery, engineering, security,
operations and assurance documentation. It separates current behaviour from
historical decisions and dated evidence so a reader can understand the service
without knowing its development history.

## Start with the question you need answered

| I need to… | Start here |
|---|---|
| Understand the product in plain English | [Root README](../README.md) |
| Review current user needs and acceptance behaviour | [Current user stories](USER_STORIES.md) |
| Understand the running system and trust boundaries | [System architecture](architecture/SYSTEM_ARCHITECTURE.md) |
| Understand BPMN and the Camunda workflow | [Workflow and Camunda guide](architecture/WORKFLOW_AND_BPMN.md) |
| See the hierarchy and every synthetic account | [Organisation and routing](architecture/ORGANISATION_AND_ROUTING.md) |
| Check what each role may do | [Role and permission matrix](reference/ROLE_PERMISSION_MATRIX.md) |
| Install the complete local stack | [Local Docker guide](deployment/LOCAL_DOCKER.md) |
| Run FastAPI or React from source | [Local source development](deployment/LOCAL_SOURCE_DEVELOPMENT.md) |
| Configure environment variables | [Configuration reference](deployment/CONFIGURATION_REFERENCE.md) |
| Qualify a release candidate | [Release runbook](deployment/RELEASE_RUNBOOK.md) |
| Respond to an incident | [Support and incident runbook](operations/SUPPORT_AND_INCIDENT_RUNBOOK.md) |
| Back up, restore or maintain data | [Backup, restore and maintenance](operations/BACKUP_RESTORE_AND_MAINTENANCE.md) |
| Review security design and evidence | [SECURITY.md](../SECURITY.md), [threat models](threat-model/), [security evidence](assurance/SECURITY_SCAN_EVIDENCE.md) |
| Review accessibility design, evidence and remaining human acceptance | [Accessibility and WCAG 2.2 evidence](assurance/ACCESSIBILITY_EVIDENCE.md) |
| See what is not ready for production | [Enterprise readiness gap register](ENTERPRISE_READINESS_GAP_REGISTER.md) |
| See current delivery status | [Master implementation plan](MASTER_IMPLEMENTATION_PLAN.md) |
| Understand how the codebase developed | [Development story](DEVELOPMENT_STORY.md) |

## A five-minute reading path

### Product owner or non-technical stakeholder

1. Read [What the product does](../README.md#what-the-product-does).
2. Follow the two diagrams in
   [How a request moves](../README.md#how-a-request-moves-through-the-service).
3. Review [Current user stories](USER_STORIES.md).
4. Check the [known production boundaries](../README.md#known-production-boundaries).

### Operational user or trainer

1. Find the role in [Who uses it](../README.md#who-uses-it).
2. Read the applicable section of [Current user stories](USER_STORIES.md).
3. Use [Workflow and Camunda](architecture/WORKFLOW_AND_BPMN.md) for routing,
   information, rework and release paths.
4. Use [Organisation and routing](architecture/ORGANISATION_AND_ROUTING.md) for
   teams, accounts and test logins.

### Developer or architect

1. Read [System architecture](architecture/SYSTEM_ARCHITECTURE.md).
2. Open the editable
   [Structurizr workspace](architecture/structurizr/workspace.dsl).
3. Read the ADRs linked from the architecture section being changed.
4. Use the applicable specification and threat model before editing code.
5. Follow [Local source development](deployment/LOCAL_SOURCE_DEVELOPMENT.md).

### Security reviewer

1. Read [SECURITY.md](../SECURITY.md) for reporting and repository policy.
2. Review the [trust boundaries](architecture/SYSTEM_ARCHITECTURE.md#10-trust-boundaries).
3. Review all [threat models](threat-model/).
4. Compare controls with the [role matrix](reference/ROLE_PERMISSION_MATRIX.md).
5. Check the dated [security scan evidence](assurance/SECURITY_SCAN_EVIDENCE.md)
   and [security matrix](assurance/SECURITY_MATRIX_EVIDENCE.md).

### Accessibility reviewer

1. Start with the current [accessibility position and WCAG 2.2 evidence](assurance/ACCESSIBILITY_EVIDENCE.md).
2. Review the inclusive acceptance criteria in the [current user stories](USER_STORIES.md).
3. Check the accessibility gates in the [Definition of Done matrix](assurance/DEFINITION_OF_DONE_MATRIX.md#accessibility-compatibility-and-performance-gates).
4. Confirm the remaining manual and representative-user work in the [production gates](deployment/PRODUCTION_GATES.md).
5. Record named review results in the [acceptance record](assurance/ACCEPTANCE_RECORD.md).

### Operator or evaluator

1. Choose a [deployment path](deployment/README.md).
2. Apply the [configuration reference](deployment/CONFIGURATION_REFERENCE.md).
3. Use the [release runbook](deployment/RELEASE_RUNBOOK.md).
4. Keep the [support](operations/SUPPORT_AND_INCIDENT_RUNBOOK.md),
   [configuration](operations/CONFIGURATION_AND_ROUTING_RUNBOOK.md) and
   [recovery](operations/BUSINESS_CONTINUITY_AND_DISASTER_RECOVERY.md) guides
   available.

## Current architecture views

The architecture uses several focused C4/Structurizr-style views. Each diagram
answers one question and avoids placing the entire system on one canvas.

| View | Question answered | Detailed guide |
|---|---|---|
| [System context](assets/architecture/01-system-context.svg) | Who uses ISTARI and what systems sit around it? | [System architecture](architecture/SYSTEM_ARCHITECTURE.md#2-system-context) |
| [Container view](assets/architecture/02-container-view.svg) | What runs and how do containers communicate? | [Executable components](architecture/SYSTEM_ARCHITECTURE.md#3-executable-components) |
| [Routing workflow](assets/architecture/03-routing-workflow.svg) | How does a Customer request reach a team? | [Routing the request](architecture/WORKFLOW_AND_BPMN.md#routing-the-request) |
| [Delivery workflow](assets/architecture/04-delivery-workflow.svg) | How is the product produced, checked and released? | [Producing and releasing](architecture/WORKFLOW_AND_BPMN.md#producing-and-releasing-the-product) |
| [Durable command](assets/architecture/05-durable-workflow-command.svg) | How do PostgreSQL and Camunda remain aligned? | [How ISTARI and Camunda share responsibility](architecture/WORKFLOW_AND_BPMN.md#how-istari-and-camunda-share-responsibility) |
| [Organisation hierarchy](assets/architecture/06-organisation-routing.svg) | Which branches are visible and selectable? | [Organisation and routing](architecture/ORGANISATION_AND_ROUTING.md) |

The editable C4 model is
[`architecture/structurizr/workspace.dsl`](architecture/structurizr/workspace.dsl).
The SVG files are committed so GitHub and offline readers can see the diagrams
without a separate rendering service.

## Current-state authorities

These documents describe how the service works now.

| Subject | Authority |
|---|---|
| Product overview, setup and engineering entry point | [Root README](../README.md) |
| Role needs, outcomes, permission failures and acceptance scenarios | [Current user stories](USER_STORIES.md) |
| Components, data authorities, trust boundaries, failure and scaling | [System architecture](architecture/SYSTEM_ARCHITECTURE.md) |
| Human tasks, BPMN paths, loops and Camunda responsibilities | [Workflow and Camunda](architecture/WORKFLOW_AND_BPMN.md) |
| Organisation tree, scope rules and complete synthetic-user directory | [Organisation and routing](architecture/ORGANISATION_AND_ROUTING.md) |
| Role and action permissions | [Role and permission matrix](reference/ROLE_PERMISSION_MATRIX.md) |
| Environment variables and invariants | [Configuration reference](deployment/CONFIGURATION_REFERENCE.md) |
| Current delivery status and next work | [Master implementation plan](MASTER_IMPLEMENTATION_PLAN.md) |
| Production blockers and accountable decisions | [Enterprise readiness gap register](ENTERPRISE_READINESS_GAP_REGISTER.md) |
| Accessibility controls, technical evidence and open human review | [Accessibility and WCAG 2.2 evidence](assurance/ACCESSIBILITY_EVIDENCE.md) |

Current-state guides state current behaviour directly. Delivery history and
superseded decisions do not appear in task guidance.

## Documentation types

The repository keeps different document types because they answer different
questions.

### Current guides

Current guides explain what exists and how to use or operate it. They are updated
when behaviour changes.

- [Root README](../README.md)
- [Documentation home](README.md)
- [Current user stories](USER_STORIES.md)
- [Architecture](architecture/)
- [Deployment](deployment/)
- [Operations](operations/)
- [Reference](reference/)

### Specifications

Specifications define detailed behaviour and acceptance criteria. They are
implementation records and may use requirement identifiers needed for
traceability. The current guides are the preferred reading path for stakeholders.

Key specifications include:

- [Structured service request MVP](specs/service-request-mvp.md)
- [Action deep links and workspace navigation](specs/action-deep-links-and-workspace-navigation.md)
- [Customer intake and account requests](specs/customer-intake-and-account-requests.md)
- [Requester cancellation and profiles](specs/requester-cancellation-and-personal-profiles.md)
- [Manual related records](specs/manual-related-records.md)
- [Tracking lifecycle and analytical visuals](specs/tracking-lifecycle-and-analytical-visuals.md)
- [Hierarchical operational overviews](specs/hierarchical-operational-overviews.md)
- [Personalised overview and navigation](specs/personalised-overview-and-primary-navigation.md)
- [Team-visible personal calendar events](specs/team-visible-personal-calendar-events.md)
- [Team operations workspace](specs/team-operations-workspace-evolution.md)
- [Unified organisation workspaces](specs/unified-organisation-workspaces.md)
- [Platform administration](specs/platform-administration-mvp.md)
- [Configuration administration usability](specs/configuration-administration-usability.md)
- [Access assistance and classification](specs/access-assistance-and-global-classification.md)
- [Request coordination language and ownership](specs/request-coordination-language-and-ownership.md)
- [Security remediation](specs/security-remediation-2026-08.md)
- [Runtime scaling and worker hardening](specs/runtime-scaling-and-worker-hardening.md)
- [Operational readiness](specs/operational-readiness.md)

The [specification traceability record](assurance/SPECIFICATION_TRACEABILITY.md)
maps requirements to implementation and evidence.

### Architecture decision records

ADRs explain decisions that would be expensive to reverse. They retain the
decision context and alternatives considered. That historical context is useful
inside a decision record but is not repeated in current product guides.

The numbered set in [`adr/`](adr/) covers:

- application, workflow and modular boundaries;
- durable Camunda commands and data-driven routing;
- administration, management grants and scoped statistics;
- calendars, boards, clarification and team membership;
- related-request evidence and step-up authentication;
- product storage, quarantine and dissemination;
- configuration sealing, approval and version pinning;
- worker fencing, runtime hardening and login throttling;
- Customer intake, cancellation and role-specific overviews;
- organisation workspaces, classification and plain-language ownership; and
- action-oriented team workspace design.

### Threat models and security reference

Threat models are current risk and control authorities:

- [Service request and product workflow](threat-model/service-request-workflow.md)
- [Platform administration](threat-model/platform-administration.md)
- [Management and analytics](threat-model/management-and-analytics.md)
- [Team workspaces and calendars](threat-model/team-workspaces-and-calendars.md)
- [Operations and recovery](threat-model/operations-and-recovery.md)
- [Audit event catalogue](security/AUDIT_EVENT_CATALOGUE.md)
- [Licence policy](security/LICENCE_POLICY.md)

### Dated assurance evidence

Assurance files preserve what was tested, scanned or rehearsed at a point in time.
They do not override current architecture or status.

| Evidence group | Records |
|---|---|
| Browser and accessibility | [Browser and workflow](assurance/BROWSER_AND_WORKFLOW_EVIDENCE.md), [accessibility](assurance/ACCESSIBILITY_EVIDENCE.md) |
| Security | [Security scans](assurance/SECURITY_SCAN_EVIDENCE.md), [security matrix](assurance/SECURITY_MATRIX_EVIDENCE.md), [log minimisation](assurance/LOG_DATA_MINIMISATION_EVIDENCE.md) |
| Data and recovery | [Migration and restore](assurance/MIGRATION_AND_RESTORE_EVIDENCE.md), [recovery](assurance/RECOVERY_EVIDENCE.md) |
| Performance | [Performance evidence](assurance/PERFORMANCE_EVIDENCE.md) |
| Configuration | [Configuration and routing](assurance/CONFIGURATION_AND_ROUTING_EVIDENCE.md) |
| Acceptance | [Definition of Done](assurance/DEFINITION_OF_DONE_MATRIX.md), [final audit](assurance/FINAL_COMPLETION_AUDIT.md), [acceptance record](assurance/ACCEPTANCE_RECORD.md) |
| Source control | [Source-control baseline](assurance/SOURCE_CONTROL_BASELINE.md) |

An evidence file may mention the exact database, browser or candidate version
used for that rehearsal. Treat that as a dated fact, not a current installation
instruction.

## Deployment and operations map

### Deployment

| Environment | Guide | Boundary |
|---|---|---|
| Local Docker Compose | [Local Docker](deployment/LOCAL_DOCKER.md) | Implemented, loopback-only, synthetic data |
| Local source development | [Source development](deployment/LOCAL_SOURCE_DEVELOPMENT.md) | Implemented developer workflow |
| AWS private VM | [AWS sandbox](deployment/AWS_SANDBOX.md) | Synthetic evaluation only |
| GCP private VM | [GCP sandbox](deployment/GCP_SANDBOX.md) | Synthetic evaluation only |
| Azure private VM | [Azure sandbox](deployment/AZURE_SANDBOX.md) | Synthetic evaluation only |
| Kubernetes | [Target design](deployment/KUBERNETES_TARGET.md) | Design only, not implemented or validated |

Use the [production gates](deployment/PRODUCTION_GATES.md) before any real-data or
connected-environment decision.

### Operations

- [Support and incident response](operations/SUPPORT_AND_INCIDENT_RUNBOOK.md)
- [Configuration and routing administration](operations/CONFIGURATION_AND_ROUTING_RUNBOOK.md)
- [Backup, restore and maintenance](operations/BACKUP_RESTORE_AND_MAINTENANCE.md)
- [Business continuity and disaster recovery](operations/BUSINESS_CONTINUITY_AND_DISASTER_RECOVERY.md)

These are procedures. Executed results belong in assurance and policy decisions
belong in current authorities or ADRs.

## Enterprise readiness at a glance

The local implementation has strong technical foundations: human-led workflow,
server-enforced permissions, durable commands, effective-dated configuration,
managed product quarantine, high automated coverage, security scanning and local
recovery evidence.

It does not yet provide an approved production identity model, managed product
storage adapter, infrastructure as code, validated high-availability topology,
accepted service levels, production monitoring ownership, real-data governance or
connected-environment acceptance. The
[gap register](ENTERPRISE_READINESS_GAP_REGISTER.md) is the authority for these
open decisions.

## Document maintenance rules

### Put a fact in one place

| Information | Maintain it in |
|---|---|
| Current product behaviour | Root README, user stories and applicable current guide |
| Detailed acceptance requirement | Applicable file in `specs/` |
| Current architecture | `architecture/SYSTEM_ARCHITECTURE.md` or `architecture/WORKFLOW_AND_BPMN.md` |
| Organisation and synthetic roster | `architecture/ORGANISATION_AND_ROUTING.md` |
| Current work and blockers | `MASTER_IMPLEMENTATION_PLAN.md` and the gap register |
| Chronological implementation history | `DEVELOPMENT_STORY.md` |
| Expensive-to-reverse decision | Numbered ADR |
| Security risk and control | Applicable threat model |
| Reproducible operational procedure | `deployment/` or `operations/` |
| Executed test, scan or rehearsal | Dated file in `assurance/` |

Link to the authority rather than copying long status or configuration passages.
Use current labels and behaviour. If chronology matters, put it in the
development story.

### Documentation length

Markdown documentation is exempt from the 350-line source limit. A coherent
guide may exceed 400 lines when headings, contents and links keep it usable. Do
not split a guide merely to satisfy a source-code line rule.

### Required checks

Run these before documentation review:

```powershell
pnpm documentation
pnpm terminology
```

The checks detect broken relative links, duplicate maintained passages and
prohibited application terminology. Also run `pnpm check` when documentation
changes executable scripts, contracts or repository policy.

Use UK English. Keep every example synthetic. Never add credentials, private
addresses, real service names, real content or production topology details to
this public-safe repository.
