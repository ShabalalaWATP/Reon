# Structurizr architecture model

Status: current editable C4 model
Last reviewed: 14 August 2026

[`workspace.dsl`](workspace.dsl) is the machine-readable architecture source for
Mist Service. It describes the system context, runtime containers, web and API
components, an end-to-end delivery interaction and the two documented executable
deployment shapes.

## Views

| Key | Purpose |
|---|---|
| `SystemContext` | People, Mist and Camunda trust relationships |
| `Containers` | Web, API, worker, PostgreSQL, product storage and scanner |
| `WebComponents` | Routing shell, feature modules, auth/context and typed API state |
| `ApiComponents` | HTTP, services, policies, ports, composition and adapters |
| `RequestDelivery` | Request submission through accepted dissemination |
| `LocalDeployment` | Docker Compose on Windows, macOS or Linux |
| `PrivateCloudDeployment` | The synthetic stack on one private AWS or GCP VM |

The SVGs in [`docs/assets/architecture`](../../assets/architecture/) are curated
repository diagrams for Markdown readers. The DSL is the editable architecture
model and must be updated whenever a material runtime boundary changes.

## Validate and render

Use an organisation-approved Structurizr CLI installation. From this directory:

```powershell
structurizr-cli validate -workspace workspace.dsl
structurizr-cli export -workspace workspace.dsl -format mermaid -output generated
```

Do not commit generated exports automatically. Review labels, scope and data
classification before replacing curated diagrams. A rendering tool is not an
architecture authority: the executable code, migration head and deployment
configuration must still agree with this model.
