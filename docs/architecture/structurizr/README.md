# Structurizr architecture model

Status: current editable C4 and custom-view model

Last reviewed: 18 August 2026

[`workspace.dsl`](workspace.dsl) is the machine-readable architecture source for
Mist Service. It models the browser and API boundary, capability composition,
focused application ports, PostgreSQL authority, the fenced worker, analytics,
managed products, Camunda-owned state, the scanner boundary, organisation
routing and both documented deployment shapes.

The workspace has no remote theme. The renderer enforces no network, a read-only
container filesystem, no Linux capabilities, `no-new-privileges`, an
unprivileged user and bounded process, memory, CPU and temporary-storage limits.
It mounts only `workspace.dsl` into Structurizr and the fresh task directory into
each rendering stage, so ignored repository files and `.git` are outside the
container boundary. The checked-in SVGs are generated from seven named views by
[`render-svg.ps1`](render-svg.ps1); they are not separate hand-authored diagrams.

## View catalogue

| Key | Type | Purpose | Checked-in SVG |
|---|---|---|---|
| `SystemContext` | System context | People, Mist, Camunda and scanner trust relationships | `01-system-context.svg` |
| `Containers` | Container | Web, API, worker, operator commands, PostgreSQL, product storage and external services | `02-container-view.svg` |
| `RoutingWorkflow` | Dynamic | Submission, durable process start and exact-child organisation routing | `03-routing-workflow.svg` |
| `DeliveryWorkflow` | Dynamic | Assignment, production, scanning, independent review, dissemination and acceptance | `04-delivery-workflow.svg` |
| `DurableWorkflowCommand` | Dynamic | Transactional intent, fenced dispatch, proof and reconciliation | `05-durable-workflow-command.svg` |
| `OrganisationRouting` | Custom | Representative JIOC, command, Ops and delivery-team hierarchy | `06-organisation-routing.svg` |
| `ScannerSupplyChain` | Container | Fail-closed scanning, signature hand-off and the updater's sole outbound HTTPS trust boundary | `07-scanner-supply-chain.svg` |
| `WebComponents` | Component | Route policy, features, session context and typed API state | Not checked in |
| `ApiComponents` | Component | HTTP composition, services, policies, ports and adapters | Not checked in |
| `WorkerComponents` | Component | Lease loop and workflow, projection, security and product jobs | Not checked in |
| `LocalDeployment` | Deployment | Docker Compose topology on a developer workstation | Not checked in |
| `PrivateCloudDeployment` | Deployment | Synthetic Compose topology on one private Linux VM | Not checked in |

The seven generated files are stored in
[`docs/assets/architecture`](../../assets/architecture/). The component and
deployment views remain available to Structurizr exporters for engineering
inspection without expanding every Markdown page.

## Reproducible toolchain

The repository pins both multi-platform Docker image digests:

- Structurizr `2026.06.28`, libraries `6.2.2`:
  `structurizr/structurizr@sha256:251905a1a2d73195e84b784966babc71b329223fdbb25368261a9e3ba39041c4`;
- PlantUML `1.2026.6`:
  `plantuml/plantuml@sha256:47870c1f76cfb3747bc7090bfe83013a4e3105b5a0bb1515e2baf5d3e2b3ee9d`.

The retired `structurizr-cli` executable is not required. On this repository's
validated Windows path, `structurizr`, Graphviz `dot` and `xmllint` were not
installed as host commands. Docker Desktop, PowerShell and the pinned images are
the supported local path.

## Validate

From the repository root:

```powershell
pwsh -NoProfile -File .\docs\architecture\structurizr\render-svg.ps1 -ValidateOnly
```

The script runs the equivalent pinned command:

```powershell
$workspace = (Resolve-Path .\docs\architecture\structurizr\workspace.dsl).Path
docker run --rm `
  --network none --read-only --cap-drop ALL `
  --security-opt no-new-privileges --pids-limit 256 --memory 1g --cpus 2 `
  --user 65532:65532 --env HOME=/tmp `
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=67108864 `
  --mount "type=bind,source=${workspace},target=/workspace/workspace.dsl,readonly" `
  structurizr/structurizr@sha256:251905a1a2d73195e84b784966babc71b329223fdbb25368261a9e3ba39041c4 `
  validate -w /workspace/workspace.dsl
```

A valid workspace exits with status zero and no validation messages.

To validate the workspace, regenerate all seven views in the sandbox and fail if
any committed SVG differs byte-for-byte, run:

```powershell
pwsh -NoProfile -File .\docs\architecture\structurizr\render-svg.ps1 -Check
```

## Export and render the seven SVGs

From the repository root:

```powershell
pwsh -NoProfile -File .\docs\architecture\structurizr\render-svg.ps1
```

The script performs these deterministic stages:

1. validate `workspace.dsl` with the pinned Structurizr image;
2. export every view as `plantuml/structurizr` into a fresh temporary directory;
3. render the seven named presentation views as SVG with the pinned PlantUML
   image;
4. copy only the seven mapped SVGs into `docs/assets/architecture`; and
5. remove the verified task-owned temporary directory.

Do not edit the generated SVGs. Change the model, relationships, view selection
or styles in `workspace.dsl`, then rerun the script. PlantUML export is a static
presentation format and supports fewer rendering features than the Structurizr
viewer, so the script and Markdown rendering must both be checked after material
layout changes.

The Docker-enabled container-validation workflow runs `-Check` for every push,
pull request and scheduled validation. The ordinary documentation gate still
performs fast link, presence and passive-content checks without requiring Docker.
