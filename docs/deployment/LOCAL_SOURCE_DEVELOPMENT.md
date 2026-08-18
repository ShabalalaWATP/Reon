# Local source development

Use this path when changing API or web code. The full Compose path remains the
easiest way to supply PostgreSQL, Camunda and ClamAV.

Use [Host setup](HOST_SETUP.md) for Windows, Intel or Apple-silicon MacBook and
Linux runtime preparation before following this source-specific path.

## Prerequisites

- Python 3.12 or later and `uv`
- Node.js 22 or later, pnpm 11.21.0 and the `corepack` command. Install an
  approved Corepack package when the Node distribution does not bundle it.
- Docker Compose v2
- PowerShell 7.4 or later
- Git

Verify versions:

```powershell
python --version
uv --version
node --version
corepack enable
pnpm --version
docker compose version
pwsh --version
```

## Install dependencies

From the repository root:

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/api --all-groups --frozen
Copy-Item .env.example .env
```

On macOS/Linux, use `cp .env.example .env`. Configure `.env` as described in the
[configuration reference](CONFIGURATION_REFERENCE.md).

## Recommended hybrid workflow

1. Start the complete dependency stack once:

   ```powershell
   pwsh -File ./scripts/start-local.ps1
   ```

2. Stop the containerised web service before running Vite:

   ```powershell
   docker compose stop web
   pnpm --filter @mist-service/web dev
   ```

   Vite serves the development frontend according to its package configuration.
   Confirm the URL printed by Vite. Browser API requests expect the configured
   development proxy/same-origin boundary; do not point React directly at
   Camunda.

   The proxy defaults to `http://localhost:8000`. For an isolated source API on
   another local port, set `MIST_API_PROXY` in the Vite process environment,
   for example `http://localhost:18000`. This is a development-build input, not
   a browser-exposed API credential.

3. For API source work, stop the containerised API and web services. The source
   process must use host-reachable dependency addresses rather than Compose DNS.
   Create a separate untracked `.env.source` with:

   ```dotenv
   ENVIRONMENT=local
   DATABASE_URL=postgresql+asyncpg://<runtime-user>:<url-encoded-password>@127.0.0.1:5432/mist_service
   CAMUNDA_REST_ADDRESS=http://127.0.0.1:8080
   WEB_ORIGIN=http://localhost:5173
   TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   ALLOWED_HOSTS=localhost,127.0.0.1
   SESSION_COOKIE_SECURE=false
   ALLOW_DEMO_USERS=true
   DEMO_USER_PASSWORD=admin
   AUDIT_HMAC_KEY=<unique-local-value-at-least-32-bytes>
   SECURITY_PSEUDONYM_KEY=<different-stable-local-value-at-least-32-bytes>
   SECURITY_PSEUDONYM_KEY_ID=stable-v1
   MANAGED_PRODUCTS_ENABLED=false
   ```

   ClamAV is not published to the host by the supplied Compose file, so this
   source-API path disables managed products. Use the complete containerised API
   for upload and product-lifecycle development unless a reviewed local override
   exposes a scanner. Never bypass scanning. If a product runtime is injected in
   tests, its host storage is separate from the Compose product volume.

4. The dependency stack has already run its one-shot migration. Start the source
   API with the runtime URL in `.env.source`:

   ```powershell
   uv run --directory apps/api --env-file ../../.env.source uvicorn mist_service.main:app --reload
   ```

   When qualifying a migration against a separate host-reachable database,
   create an untracked `.env.migrate` whose `DATABASE_URL` uses the migration
   owner and which includes `APP_RUNTIME_DATABASE_USER`,
   `APP_BACKUP_DATABASE_USER` and `APP_MAINTENANCE_DATABASE_USER`. The
   migration environment uses `DATABASE_URL`, not `MIGRATION_DATABASE_URL`,
   because these commands run outside Compose. Then run:

   ```powershell
   uv run --directory apps/api --env-file ../../.env.migrate alembic upgrade head
   uv run --directory apps/api --env-file ../../.env.migrate python -m mist_service.postgres_permissions
   ```

   Stop using the migration environment immediately afterwards. The running API
   must use `.env.source` and its runtime identity.

5. The API never runs projection or outbox maintenance. When changing worker
   code, stop the containerised worker and run the source entry point with the
   same host-reachable dependencies:

   ```powershell
   docker compose stop worker
   uv run --directory apps/api --env-file ../../.env.source mist-worker
   ```

   Restore the Compose worker after the source process stops. Never run a source
   worker with migration-owner credentials. The worker's only optional flag is
   `--once`, which performs one leased iteration and exits. Use it only while the
   Compose worker remains stopped; it is not a migration or readiness shortcut.

Never start multiple replicas that all attempt the migration. The Docker image
does not auto-migrate; Compose uses its explicit one-shot `migrator` service.

## Tests and checks

Fast feedback:

```powershell
pnpm --filter @mist-service/web test
uv run --directory apps/api pytest
```

Complete static and policy checks:

```powershell
pnpm check
uv run --directory apps/api ruff format --check .
uv run --directory apps/api ruff check .
uv run --directory apps/api mypy
uv run --directory apps/api bandit -c pyproject.toml -r src alembic
uv run --directory apps/api pip-audit
pnpm --filter @mist-service/web build
```

Coverage gates are 95 per cent lines and branches independently for backend and
frontend application code. Do not lower them to accept a change.

## Database and workflow changes

- Create an Alembic revision for every schema change and test both empty-database
  migration and previous-head upgrade.
- Validate BPMN with `pwsh -File workflow/validate-bpmn.ps1`.
- Deploy local BPMN through `scripts/start-local.ps1`; it records the checksum,
  process identity and operator attestation.
- Never edit Camunda tables or fabricate workflow position in PostgreSQL.
- Never reseal or backdate an approved configuration to repair a test fixture.

## Before handing off

Run `git status --short`, inspect only your intended changes, run the relevant
tests and update a specification, ADR or threat model when the change affects
behaviour, architecture or security.
