# Configuration reference

Status: current application and local Compose settings

Settings are read from environment variables through Pydantic. Variable names
are case-insensitive in the API, but deployments should use the uppercase names
below. `.env.example` is a local template only. Never commit `.env`, resolved
Compose output, passwords, session cookies or connection strings.

## General rules

- `ENVIRONMENT` is `local`, `test` or `prod`.
- `prod` activates validation constraints; it does not provide missing OIDC,
  product-storage or infrastructure integrations.
- Comma-separated lists are trimmed. Do not use `*` for hosts or origins.
- Database URL passwords must be URL encoded when they contain reserved URI
  characters.
- Secrets should come from the platform secret manager in a connected target,
  not a ConfigMap, image, Git variable or command line.

## Application database

| Variable | Local default/example | Meaning and constraint |
|---|---|---|
| `DATABASE_URL` | runtime role at `postgres:5432` | SQLAlchemy async URL. Production requires `postgresql+asyncpg` and the asyncpg-compatible query parameter `ssl=verify-full`. |
| `DATABASE_POOL_SIZE` | `20` | Retained connections per API process, 1 to 50. |
| `DATABASE_MAX_OVERFLOW` | `30` | Temporary connections per API process, 0 to 50. |

Total API connection demand is approximately `replica count × (pool size + max
overflow)`. Reserve separate capacity for migrations, backups and operators.

## Maintenance worker

| Variable | Default | Meaning and constraint |
|---|---|---|
| `WORKER_DATABASE_POOL_SIZE` | `5` in Compose | Retained connections for each worker process. Compose maps it to the worker's `DATABASE_POOL_SIZE`. |
| `WORKER_DATABASE_MAX_OVERFLOW` | `5` in Compose | Temporary worker connections. Add these separately to the total database budget. |
| `WORKER_HEALTH_REQUIRED` | `true` in Compose and production | Requires a fresh durable heartbeat for API readiness. Production rejects `false`. |
| `WORKER_INTERVAL_SECONDS` | `0.5` | Idle polling interval, 0.05 to 30 seconds. Work-bearing iterations continue without the idle delay. |
| `WORKER_LEASE_SECONDS` | `30` | Named job lease duration, 5 to 300 seconds. Long jobs renew before expiry. |
| `WORKER_HEARTBEAT_STALE_SECONDS` | `10` | Maximum accepted heartbeat age, 2 to 600 seconds. |

The worker and API use the runtime database role, never the migration owner.
Every worker replica may run the same executable because singleton jobs compare
name, owner and generation. Size the combined API and worker pools below the
database limit and alert on stale heartbeats, repeated lease loss and content-
free job failure codes.

Local PostgreSQL initialisation additionally uses:

| Variable | Purpose |
|---|---|
| `POSTGRES_ADMIN_PASSWORD` | Bootstrap superuser only; not an API credential. |
| `APP_DATABASE_NAME` | Application database name. |
| `APP_DATABASE_USER` / `APP_DATABASE_PASSWORD` | Schema/migration owner used by the one-shot migrator. |
| `APP_RUNTIME_DATABASE_USER` / `APP_RUNTIME_DATABASE_PASSWORD` | Least-privileged API role. |
| `APP_BACKUP_DATABASE_USER` / `APP_BACKUP_DATABASE_PASSWORD` | Read-only dump role. |
| `MIGRATION_DATABASE_URL` | Async URL for the migration owner, consumed by the migrator. |

Every local database identity and password must be distinct. Production database
provisioning is not supplied by Compose.

## Camunda

| Variable | Default/example | Meaning and constraint |
|---|---|---|
| `CAMUNDA_REST_ADDRESS` | `http://orchestration:8080` in Compose | Base Orchestration Cluster API address. Production must be HTTPS. `CAMUNDA_BASE_URL` remains an input alias. |
| `CAMUNDA_PROCESS_ID` | `service-request-v1` | Expected BPMN process definition identifier. Forwarded by Compose. |
| `CAMUNDA_AUTH_MODE` | `NONE` locally | Only `NONE` and `BASIC` are implemented. Production rejects `NONE`. |
| `CAMUNDA_USERNAME` | empty locally | Required with non-empty password for `BASIC`. |
| `CAMUNDA_PASSWORD` | empty locally | Secret for `BASIC`. |

Local Compose intentionally overrides the API address and auth mode to internal
HTTP and `NONE`. It also provisions `CAMUNDA_DATABASE_NAME`,
`CAMUNDA_DATABASE_USER`, `CAMUNDA_DATABASE_PASSWORD`, and optional host ports
`CAMUNDA_HOST_PORT` (8080) and `CAMUNDA_MANAGEMENT_HOST_PORT` (9600).

The client has no OIDC client-credentials implementation. `BASIC` is a narrow
compatibility option, not an accepted enterprise identity design.

## Browser, host and session security

| Variable | Default | Meaning and constraint |
|---|---|---|
| `WEB_ORIGIN` | `http://localhost:5173` | Canonical browser origin, automatically included in trusted origins. Production requires HTTPS. |
| `TRUSTED_ORIGINS` | local loopback origins | Exact comma-separated CORS/CSRF origins. Production requires HTTPS. |
| `ALLOWED_HOSTS` | derived plus explicit local hosts | Exact trusted Host header names. Production requires a non-empty wildcard-free list. |
| `SESSION_COOKIE_SECURE` | `false` locally | Must be `true` in production. |
| `SESSION_COOKIE_NAME` | `istari_session` | Cookie name. Plan changes carefully because they invalidate existing sessions. |
| `SESSION_COOKIE_SAMESITE` | `lax` | `lax` or `strict`; `none` is intentionally rejected. |
| `SESSION_TTL_SECONDS` | `28800` | Absolute lifetime, 300 to 86400 seconds. Forwarded by Compose. |
| `SESSION_IDLE_SECONDS` | `3600` | Idle lifetime, 60 to 86400 seconds. Forwarded by Compose. |
| `ADMIN_ELEVATION_SECONDS` | `300` | Privileged step-up window, 60 to 900 seconds. Forwarded by Compose. |
| `MAX_REQUEST_BODY_BYTES` | `1048576` | Ordinary request-body limit, 1 KiB to 10 MiB. |

The current application login is local database authentication. OIDC, MFA,
claims mapping and identity bootstrap are not implemented.

### Login resource protection

| Variable | Default | Meaning and constraint |
|---|---|---|
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | `60` | Shared fixed-window duration, 10 to 3,600 seconds. |
| `LOGIN_RATE_LIMIT_PER_SOURCE` | `30` | Attempts permitted per one-way source digest in each window, 1 to 1,000. |
| `LOGIN_RATE_LIMIT_GLOBAL` | `300` | Attempts permitted across all API replicas in each window, 1 to 10,000 and never below the source limit. |
| `LOGIN_RATE_LIMIT_TIMEOUT_SECONDS` | `3` | End-to-end deadline for connection acquisition and durable budget consumption, 0.25 to 10 seconds. PostgreSQL transaction-local statement and row-lock deadlines are set below this value. |
| `LOGIN_HASH_CONCURRENCY` | `2` | Maximum simultaneous Argon2 operations in each API process, 1 to 16. |
| `TRUSTED_PROXY_CIDRS` | empty | Comma-separated direct-peer networks permitted to supply exactly one `X-Forwarded-For` address. Use canonical CIDR notation and configure only networks owned by the ingress tier. |

The limiter durably consumes both PostgreSQL budgets in its own short transaction
before account lookup and returns one generic `429` with `Retry-After`. The
global row lock is released before Argon2 begins, and caller cancellation cannot
discard a fast accepted attempt. Connection acquisition, statements, row-lock
waits and cancellation cleanup are bounded by the configured deadline. A timeout
returns an account-neutral `503` before account lookup or hashing. The limiter
stores no username or raw client address. An empty proxy list is the safe local
default. Do not add public or user networks to make forwarded headers appear to
work. Production still needs edge protection for volumetric attacks.

## Audit and synthetic users

| Variable | Local value | Meaning and constraint |
|---|---|---|
| `AUDIT_HMAC_KEY` | unique value of at least 32 bytes | Legacy single HMAC key for tamper-evident audit events. Required in production unless the versioned keyring is configured. |
| `AUDIT_HMAC_ACTIVE_KEY_ID` | `legacy` | Safe identifier written on new audit events and anchors. Must name a key in the configured keyring. |
| `AUDIT_HMAC_KEYRING` | JSON object of key ID to 32-byte-or-longer secret | Rotation keyring. Retain every historic key referenced by live events or backups; secrets must come from the approved secret store. |
| `ALLOW_DEMO_USERS` | `true` | Permits synthetic fixture seeding. Must be `false` in production. |
| `DEMO_USER_PASSWORD` | `admin` | Deliberately weak local-only shared fixture password. Must differ from infrastructure secrets. |

Do not set `ALLOW_DEMO_USERS=true` outside an isolated synthetic environment.

## Managed products

| Variable | Default | Meaning and constraint |
|---|---|---|
| `PRODUCT_STORAGE_PATH` | `/var/lib/istari-products` in Compose | Private filesystem root. Must be absolute in production, although the built-in runtime is still rejected there. |
| `PRODUCT_ALLOWED_EXTERNAL_DOMAINS` | `products.example.test` locally | Comma-separated exact host allowlist for HTTPS product links. |
| `PRODUCT_UPLOAD_TTL_SECONDS` | `600` | Upload-intent lifetime, 60 to 3600 seconds. |
| `PRODUCT_MAX_FILE_BYTES` | `26214400` | Per-file limit, up to 25 MiB. |
| `PRODUCT_MAX_PACKAGE_BYTES` | `104857600` | Package limit, up to 100 MiB and never below the file limit. |
| `PRODUCT_CLAMAV_HOST` | `clamav` | Non-empty scanner host. |
| `PRODUCT_CLAMAV_PORT` | `3310` | Scanner port, 1 to 65535. |
| `PRODUCT_CLAMAV_TIMEOUT_SECONDS` | `30` | Scan timeout, greater than zero and at most 120 seconds. |
| `CLAMAV_SIGNATURE_MAX_AGE_HOURS` | `48` in Compose | Maximum accepted age of the daily signature database's signed build timestamp, 1 to 168 hours. Scanner health also requires the daemon to have loaded the same version held on disk. |
| `MANAGED_FILE_UPLOADS_ENABLED` | `true` locally | Allows managed bytes when managed products are enabled. Production also requires an injected approved semantic/CDR scanner runtime. |

The untrusted-content clamd process has an internal network only and a read-only
signature mount. A separate non-root updater owns the writable signature volume
and outbound mirror access. No S3 or GCS runtime is present. Filesystem storage
and ClamAV are local
evaluation adapters, not a production product-protection architecture.

## Related-request matching

| Variable | Default | Meaning and constraint |
|---|---|---|
| `REQUEST_MATCHING_SEMANTIC_ENABLED` | `true` | Enables asynchronous semantic enrichment. Text matching and human routing continue when disabled. |
| `REQUEST_EMBEDDING_THREADS` | `2` | Worker threads available to the local ONNX runtime, 1 to 8. |
| `REQUEST_EMBEDDING_BATCH_SIZE` | `8` | Pending projections processed per fenced pass, 1 to 32. |
| `REQUEST_EMBEDDING_CACHE_PATH` | `/app/.model-cache` in the image | Offline model cache. It must be absolute in production. |
| `REQUEST_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Fixed accepted 384-dimension model. Changing it requires code, migration, provenance and re-index evidence. |

The image build resolves the accepted model revision, verifies the revision and
runtime-file SHA-256 values, then disables Hugging Face network access at
runtime. Request content is never sent to the model host. Semantic failure leaves
the transactionally created full-text projection usable and is not a routing
failure.

## Feature flags

| Variable | Secure default | Capability |
|---|---|---|
| `ACTION_WORKSPACE_ENABLED` | `false` | Personal work/action workspace. |
| `NOTIFICATIONS_ENABLED` | `false` | In-application notifications and preferences. |
| `MANAGED_PRODUCTS_ENABLED` | `false` | Managed package, review and dissemination functions. |
| `CONFIGURATION_ADMIN_ENABLED` | `false` | Effective-dated configuration administration UI/API. Active sealed configuration remains a runtime readiness requirement even when this surface is disabled. |
| `PLANNING_EVOLUTION_ENABLED` | `false` | Enhanced planning/capacity capability. |
| `STATISTICS_EVOLUTION_ENABLED` | `false` | Extended scoped statistics. |

`.env.example` enables these features for the complete synthetic demonstration.
Enable them in another environment only after its acceptance evidence and data
dependencies are ready. Feature flags reduce exposure; they are not
authorisation controls.

## Local host ports

| Variable or mapping | Default | Exposure |
|---|---|---|
| `POSTGRES_HOST_PORT` | `5432` | `127.0.0.1` only |
| `CAMUNDA_HOST_PORT` | `8080` | `127.0.0.1` only, unauthenticated |
| `CAMUNDA_MANAGEMENT_HOST_PORT` | `9600` | `127.0.0.1` only |
| API Compose mapping | `8000` | Fixed to `127.0.0.1` |
| Web Compose mapping | `5173` | Fixed to `127.0.0.1` |

`APP_DATABASE_NAME` may be paired with `POSTGRES_HOST_PORT` for host-source
development. Compose services always use container port 5432.

## Production validation summary

With `ENVIRONMENT=prod`, settings validation requires:

- demo users disabled and secure cookies;
- PostgreSQL/asyncpg with a TLS requirement in the URL;
- an HTTPS Camunda endpoint and non-`NONE` authentication;
- HTTPS browser origins and explicit allowed hosts;
- an audit HMAC key and absolute product-storage path.

Application startup then rejects its built-in production managed-product
runtime. Production still requires approved identity, product storage/scanning,
secret injection, ingress and platform implementation described in
[Production gates](PRODUCTION_GATES.md).

Production application construction also removes `/openapi.json`, `/docs` and
`/redoc`. Health and readiness routes are excluded from the schema and must be
reachable only through the private operational boundary.

## Change procedure

1. Add or change a typed setting with secure defaults and validators.
2. Forward it explicitly in every intended runtime, including Compose when
   applicable.
3. Update `.env.example` with names only and no real secrets.
4. Add local, invalid and production-invariant tests.
5. Update this reference and the threat model if the trust boundary changes.
6. Treat secret, cookie-name, origin and process-identity changes as release
   changes requiring rollback planning.
