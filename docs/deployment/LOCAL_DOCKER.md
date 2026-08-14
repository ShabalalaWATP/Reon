# Local Docker setup

Status: implemented development and synthetic-evaluation topology

## What this starts

Docker Compose starts PostgreSQL 17.10, Camunda 8.9.14, an internal ClamAV daemon
and separate signature updater, a one-shot database migrator, FastAPI, the
independent maintenance worker, the React/Nginx image and private product-storage
volumes.
Every published port is bound to `127.0.0.1`. Camunda has no authentication in
this topology. Do not change the binding to `0.0.0.0` or run it on a shared host.

Service images are digest-pinned. Long-running PostgreSQL, Camunda, API, worker
and web processes run as fixed non-root identities, with capabilities dropped
and read-only filesystems where their runtime permits it. Clamd parses untrusted
content on an internal-only network with a read-only definition mount. A
non-scanning updater alone has the outbound signature network and writable mount.

Normal first start needs at least 8 GB of memory available to Docker; more is
helpful during Camunda image build/start and the ClamAV signature initialisation.

## 1. Install prerequisites

All platforms need Git, Docker with Compose v2 and PowerShell 7.4 or later. The
guarded start and BPMN validation/deployment scripts are PowerShell scripts.

### Windows 10/11

1. Enable hardware virtualisation and WSL 2.
2. Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
   using the WSL 2 backend and Linux containers.
3. Install PowerShell 7.4 or later and Git.
4. Start Docker Desktop and wait until the engine reports ready.
5. In PowerShell, verify:

   ```powershell
   docker version
   docker compose version
   pwsh --version
   git --version
   ```

### macOS

1. Install the correct Apple silicon or Intel build of
   [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/).
2. Allocate at least 8 GB RAM to Docker Desktop when the host permits it.
3. Install Git and PowerShell 7.4 or later, for example through an organisation-
   approved package manager.
4. Start Docker Desktop, open Terminal and verify the four commands shown above.

### Linux

1. Install [Docker Engine](https://docs.docker.com/engine/install/) for the exact
   supported distribution, including the Compose plugin. Docker Desktop is also
   available through the [Linux guide](https://docs.docker.com/desktop/setup/install/linux/).
2. Configure non-root Docker access according to organisational policy. Logging
   out and back in may be required after group changes.
3. Install Git and PowerShell 7.4 or later.
4. Optionally install [uv](https://docs.astral.sh/uv/), required only for the
   `-SeedDemoData` start option described below.
5. Start Docker and verify the four commands shown above.

Review Docker Desktop licensing before enterprise or government use.

## 2. Obtain and configure the repository

```powershell
git clone <approved-repository-url> Istari-Service
Set-Location Istari-Service
Copy-Item .env.example .env
```

On macOS or Linux, the equivalent copy command is `cp .env.example .env`.

Edit `.env` and replace every `CHANGE_ME`. Use a different randomly generated
value for the bootstrap, migration-owner, runtime, backup and Camunda database
passwords. `AUDIT_HMAC_KEY` must contain at least 32 UTF-8 bytes and differ from
all passwords. Keep these local values outside source control.

For this synthetic fixture only, retain:

```dotenv
ENVIRONMENT=local
ALLOW_DEMO_USERS=true
DEMO_USER_PASSWORD=admin
SESSION_COOKIE_SECURE=false
WEB_ORIGIN=http://localhost:5173
```

Do not percent-encode a password differently between its dedicated setting and
the corresponding database URL. The guarded script requires `DATABASE_URL` to
use the runtime account and `MIGRATION_DATABASE_URL` to use the migration owner,
both at `postgres:5432` and the configured application database.

## 3. Validate and start

The recommended entry point validates placeholders, distinct identities and
secrets, URL roles and local-only origins before starting Compose:

```powershell
pwsh -File ./scripts/start-local.ps1
```

The helper runs `docker compose up --detach --wait --build`, validates and
deploys the BPMN over the internal Compose workflow network, then records
workflow availability from inside the API container. It does not depend on the
host Camunda port. Before changing anything, it inspects every deployed process
with the configured ID and downloads its XML: one exact active match is reused,
no match is deployed as version 1, and any conflict or unattested existing
definition stops fail closed. The checksum-bound attestation is required for
configuration readiness. Do not replace this with an unrecorded manual upload.

Useful variants:

```powershell
# Reuse images after source and dependency inputs are unchanged
pwsh -File ./scripts/start-local.ps1 -NoBuild

# Operate an explicitly named isolated Compose project
pwsh -File ./scripts/start-local.ps1 -ComposeProjectName istari-qa

# Only when deliberately testing without workflow deployment
pwsh -File ./scripts/start-local.ps1 -SkipWorkflowDeployment

# Also seed the synthetic request portfolio for a populated demonstration
pwsh -File ./scripts/start-local.ps1 -SeedDemoData
```

`-SeedDemoData` drives a varied set of synthetic requests through the live
workflow with the demo accounts, giving every delivery team completed and
in-flight work, then re-times the recorded history across recent weeks so the
statistics views hold believable trends. It needs `uv` on the host, waits on
the sign-in rate limiter for several minutes, and can be rerun safely: an
interrupted pass resumes instead of duplicating requests.

Compose forwards database pool, session expiry and Camunda process settings from
`.env` into the API. Check the resolved model without printing or sharing its
secret-bearing output:

```powershell
docker compose config --quiet
```

## 4. Verify the stack

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

On macOS/Linux, `curl -fsS http://127.0.0.1:8000/ready` is equivalent. Readiness
must report `ready`, with database, workflow, configuration and maintenance all
`ok` when their features are enabled.

Open [http://localhost:5173](http://localhost:5173). Synthetic accounts are
`admin1` to `admin99` with password `admin`; `admin16` is intentionally inactive.
The complete mapping is in the
[synthetic user directory](../architecture/ORGANISATION_AND_ROUTING.md#complete-synthetic-user-directory).

Run a representative Camunda exercise after a fresh setup:

```powershell
pwsh -File ./scripts/smoke-camunda.ps1
```

## 5. Logs and troubleshooting

```powershell
docker compose ps
docker compose logs --tail 200 api
docker compose logs --tail 200 worker
docker compose logs --tail 200 orchestration
docker compose logs --tail 200 postgres
docker compose logs --tail 200 clamav
docker compose logs --tail 200 clamav-updater
```

- If ClamAV is unhealthy, allow its separate updater to finish and inspect both
  logs. Health requires clamd to answer, the signed daily-definition build time
  to be within `CLAMAV_SIGNATURE_MAX_AGE_HOURS`, and the loaded and on-disk
  versions to match.
  Do not disable scanning or loosen freshness to make uploads work.
- If readiness says `workflow: unavailable`, verify Camunda health and rerun the
  guarded start for the same Compose project so validation and attestation occur
  together.
- If readiness says `configuration: unavailable` and no process definition has
  been deployed, rerun guarded startup. If an existing definition is reported,
  do not deploy another version or rewrite history. Follow the configuration
  runbook and reconcile the exact deployment evidence.
- If readiness says `maintenance: unavailable`, inspect the worker log and its
  database/Camunda dependencies. Do not start maintenance inside the API as a
  workaround.
- If a port is occupied, change only the documented host-port settings for
  PostgreSQL/Camunda. Web and API mappings are currently fixed in Compose.
- If a volume came from an incompatible older schema, preserve it until its data
  is assessed. Do not delete volumes as a routine repair.

## 6. Stop, restart and reset

Stop containers while retaining named volumes:

```powershell
docker compose stop
```

Restart the same data:

```powershell
pwsh -File ./scripts/start-local.ps1 -NoBuild
```

Remove containers and networks but retain volumes:

```powershell
docker compose down
```

`docker compose down --volumes` destroys all synthetic application, workflow,
product and scanner state. It is intentionally not a normal instruction. Use it
only for a confirmed disposable environment after resolving the exact Compose
project and accepting that it is unrecoverable without a backup.

## 7. Local backup

Named volumes are persistence, not backups. Follow
[Backup, restore and maintenance](../operations/BACKUP_RESTORE_AND_MAINTENANCE.md)
for a checksum-verified dump and isolated restoration exercise.
