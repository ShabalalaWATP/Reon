# ISTARI Service documentation

This directory is the navigation point for the synthetic ISTARI Service MVP.
Working local software is not evidence of production readiness. Documents label
implemented behaviour, tested procedures, target designs and unresolved gates
separately.

## Start here

| Need | Document |
|---|---|
| Understand the system and its trust boundaries | [System architecture](architecture/SYSTEM_ARCHITECTURE.md) |
| Install and run the complete local stack | [Local Docker guide](deployment/LOCAL_DOCKER.md) |
| Run the frontend or API from source | [Local source development](deployment/LOCAL_SOURCE_DEVELOPMENT.md) |
| Evaluate privately on AWS | [AWS synthetic sandbox](deployment/AWS_SANDBOX.md) |
| Evaluate privately on Google Cloud | [GCP synthetic sandbox](deployment/GCP_SANDBOX.md) |
| Evaluate privately on Azure | [Azure synthetic sandbox](deployment/AZURE_SANDBOX.md) |
| Understand the intended production direction | [Kubernetes target](deployment/KUBERNETES_TARGET.md) |
| Configure environment variables | [Configuration reference](deployment/CONFIGURATION_REFERENCE.md) |
| Build and qualify a release candidate | [Release runbook](deployment/RELEASE_RUNBOOK.md) |
| Decide whether a deployment may contain real data | [Production gates](deployment/PRODUCTION_GATES.md) |
| Review the current security remediation and reporting route | [August security specification](specs/security-remediation-2026-08.md), [security policy](../SECURITY.md) |
| View screenshots of the running synthetic application | [Browser and workflow evidence](assurance/BROWSER_AND_WORKFLOW_EVIDENCE.md#current-application-screenshots) |
| Find specifications, decisions and evidence | [Enterprise documentation index](ENTERPRISE_DOCUMENTATION_INDEX.md) |
| See unresolved enterprise blockers | [Enterprise readiness gap register](ENTERPRISE_READINESS_GAP_REGISTER.md) |

## Documentation model

- `specs/` defines behaviour and acceptance criteria.
- `architecture/` describes the current design, organisation and durable
  foundations.
- `adr/` records decisions that would be expensive to reverse.
- `threat-model/` and `security/` describe risks, controls and audit semantics.
- `operations/` contains procedures for a running environment.
- `deployment/` describes installation, configuration and release boundaries.
- `assurance/` contains dated evidence. It may describe an older candidate and
  must not silently override current status.
- `reference/` provides stable lookup material such as roles and mock accounts.

The [implementation plan](MASTER_IMPLEMENTATION_PLAN.md) is the current delivery
status authority. The [development story](DEVELOPMENT_STORY.md) is chronological
history, not a setup guide. Assurance, ADR and history files are retained for
traceability even after newer evidence supersedes them.

## Deployment status at a glance

| Path | Intended use | Current status |
|---|---|---|
| Docker Compose on a developer workstation | Development and synthetic evaluation | Implemented and exercised |
| Compose on a private AWS, GCP or Azure VM | Time-bounded synthetic sandbox | Documented evaluation pattern, not production |
| Kubernetes with managed dependencies | Connected staging and production target | Design only, not implemented or validated |

Do not use real service content. Production identity bootstrap and OIDC are not
implemented. Camunda client authentication supports only `NONE` and `BASIC`,
the local Camunda endpoint is deliberately unauthenticated, managed products use
local filesystem storage, and there is no S3 or GCS production runtime. There is
also no infrastructure as code or validated production topology.

## Keeping documents current

Change a durable fact at its authority and link to it elsewhere. Run the
documentation and terminology checks before review:

```powershell
pnpm documentation
pnpm terminology
```

Use UK English, synthetic examples and relative Markdown links. Never place
credentials, internal addresses, real names, screenshots containing service
content or production topology details in this public-safe repository.
