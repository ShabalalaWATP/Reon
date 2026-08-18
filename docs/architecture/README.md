# Architecture guide

Status: current architecture entry point

Last reviewed: 18 August 2026

Mist Service is a human-led request, delivery and dissemination application.
This directory separates three architecture authorities so system boundaries,
workflow rules and organisation policy do not become competing copies.

## Document authorities

| Authority | Use it for |
|---|---|
| [System architecture](SYSTEM_ARCHITECTURE.md) | Runtime containers, composition and ports, data authority, trust boundaries, worker jobs, products, analytics, recovery and deployment constraints |
| [Workflow and Camunda](WORKFLOW_AND_BPMN.md) | Human tasks, outcomes, information and rework loops, durable commands, Camunda authority and failure behaviour |
| [Organisation and routing](ORGANISATION_AND_ROUTING.md) | Configured hierarchy, direct-child selection, roles, workspaces, reporting grants and synthetic identities |

The executable code, Alembic head, BPMN contract and deployment configuration
remain the implementation authorities. The guides explain how those sources fit
together and must be updated when a material boundary or rule changes.

## Model and rendered views

The [Structurizr catalogue and reproducible commands](structurizr/README.md)
describe the editable [`workspace.dsl`](structurizr/workspace.dsl), all component
and deployment views, the pinned validation toolchain and the SVG generator.

| View | Purpose |
|---|---|
| [System context](../assets/architecture/01-system-context.svg) | People and systems around Mist |
| [Runtime containers](../assets/architecture/02-container-view.svg) | Supported application, data, workflow and scanner interfaces |
| [Routing workflow](../assets/architecture/03-routing-workflow.svg) | Customer submission through team assignment |
| [Delivery workflow](../assets/architecture/04-delivery-workflow.svg) | Product production through accepted dissemination |
| [Durable workflow command](../assets/architecture/05-durable-workflow-command.svg) | PostgreSQL to Camunda consistency pattern |
| [Organisation routing](../assets/architecture/06-organisation-routing.svg) | Representative direct-child route and first-class siblings |
| [Scanner supply chain](../assets/architecture/07-scanner-supply-chain.svg) | Product quarantine, malware scanning, signature hand-off and controlled updater egress |

The seven SVGs are generated from named Structurizr views. They must not be edited
independently. Validate without writing assets using:

```powershell
pwsh -NoProfile -File .\docs\architecture\structurizr\render-svg.ps1 -ValidateOnly
```

Regenerate the presentation set using:

```powershell
pwsh -NoProfile -File .\docs\architecture\structurizr\render-svg.ps1
```
