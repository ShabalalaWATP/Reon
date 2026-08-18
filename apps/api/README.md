# Mist Service API

This package is the browser-facing FastAPI boundary for the synthetic Mist
service-request demonstration. PostgreSQL owns product data and the stable status
projection. Camunda owns process position and human user-task lifecycle.

## Local development

From the repository root, install every locked API dependency group:

```powershell
uv sync --project apps/api --all-groups --frozen
```

The repository `.env.example` is for Compose. Its database and Camunda hosts use
Compose DNS and its `DATABASE_URL` is the runtime identity, so do not use that
file directly for a host-run API or Alembic command. Create separate untracked
`.env.source` and `.env.migrate` files as described in
[local source development](../../docs/deployment/LOCAL_SOURCE_DEVELOPMENT.md).
Run migrations with the migration-owner URL:

```powershell
uv run --directory apps/api --env-file ../../.env.migrate alembic upgrade head
uv run --directory apps/api --env-file ../../.env.migrate python -m mist_service.postgres_permissions
```

Start only the API when its PostgreSQL and Camunda dependencies are already
available:

```powershell
uv run --directory apps/api --env-file ../../.env.source uvicorn mist_service.main:app --reload
```

The repository does not yet provide one source-mode cache preparation command
that applies the image build's exact model revision and blob checks. Do not
bootstrap source mode from the mutable model alias. Keep semantic enrichment
disabled when source-running the worker; deterministic text matching remains
available:

```powershell
$env:REQUEST_MATCHING_SEMANTIC_ENABLED = "false"
$env:HF_HUB_OFFLINE = "1"
uv run --directory apps/api --env-file ../../.env.source mist-worker
```

Use the normal Compose image when semantic matching is required. It bakes and
checksum-verifies the accepted cache during its build, sets `HF_HUB_OFFLINE=1`
and runs without model-host access. A future source preparation script must reuse
that exact revision and every blob digest before this restriction is removed. A
source API and worker must use the same stable `SECURITY_PSEUDONYM_KEY` so
restart or process boundaries do not change security-event pseudonyms.

The normal full-stack entry point is the guarded helper from the repository root:

```powershell
pwsh -File ./scripts/start-local.ps1
```

It validates `.env`, starts Compose, deploys the BPMN and records workflow
availability through the API container. See the repository
[local Docker guide](../../docs/deployment/LOCAL_DOCKER.md) and
[configuration reference](../../docs/deployment/CONFIGURATION_REFERENCE.md).

Compose uses a separate one-shot `migrator` service before the API. A replicated
deployment must likewise run Alembic once as a controlled release job instead of
letting application replicas race the same schema upgrade.

## Architecture boundaries

Routes translate HTTP and depend on focused services. Services coordinate
repositories, domain/policy modules, workflow ports and product ports. PostgreSQL
is authoritative for application content, identity, audit and the stable
projection; Camunda is authoritative for process position and human-task
lifecycle. The browser never calls Camunda. The outbox, idempotent commands,
leases and reconciliation converge these two authorities without pretending
they share a transaction.

Application startup restores/seeds the sealed configuration and permits
mock-user seeding only when configured. It does not run maintenance. The
separately deployable `mist-worker` process owns workflow dispatch,
reconciliation, notification projection and due membership projection under
durable fenced leases. `/health` is liveness. `/ready` checks PostgreSQL,
workflow, configuration integrity and the worker heartbeat when required, and
fails with HTTP 503 when a required dependency is unavailable.

Login consumes global and source-specific fixed-window capacity in PostgreSQL
before account lookup and Argon2 verification. Source addresses are canonicalised
and one-way digested, forwarding is trusted only from configured proxy networks,
and every process has an independent Argon2 concurrency bound. Production API
construction disables OpenAPI, Swagger UI and ReDoc.

Read the full [system architecture](../../docs/architecture/SYSTEM_ARCHITECTURE.md).
Production identity and managed-product runtimes are not present: Camunda auth is
limited to `NONE`/`BASIC`, application OIDC/bootstrap is absent, and the built-in
filesystem/ClamAV runtime is rejected in `prod` without an approved injected
adapter.

## Quality checks

```powershell
uv run --directory apps/api pytest
uv run --directory apps/api ruff check .
uv run --directory apps/api ruff format --check .
uv run --directory apps/api mypy
uv run --directory apps/api bandit -c pyproject.toml -r src alembic
uv run --directory apps/api pip-audit
```

Pytest enforces line and branch coverage as independent 95 per cent gates. A
high combined coverage value cannot hide an under-tested branch dimension.
Migrations require an explicit `DATABASE_URL`; no database credential is stored
in this package.

For release sequencing, PostgreSQL qualification and target-platform gates, see
the [release runbook](../../docs/deployment/RELEASE_RUNBOOK.md) and
[production gates](../../docs/deployment/PRODUCTION_GATES.md).
