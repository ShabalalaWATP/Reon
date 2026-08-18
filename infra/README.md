# Local infrastructure boundary

This Compose topology is for local development and evaluation only. It binds
PostgreSQL, the Camunda API, the product API and the web application to the host
loopback interface. The Camunda V2 API is intentionally unprotected locally.

PostgreSQL 17.10 uses a bootstrap superuser only to initialise two separately owned
databases. The application role cannot own or migrate Camunda storage, and the
Camunda role cannot own or migrate product data. Named volumes retain PostgreSQL
and Camunda engine state across normal container recreation.

The bootstrap helper prepares volume ownership, then the database runs as UID
70 without `gosu`. API, worker, Camunda and Nginx runtimes also use fixed
non-root identities with dropped capabilities and no-new-privileges. Nginx
listens on container port 8080 and writes only to `/tmp` under a read-only root
filesystem.

ClamAV is split into two least-privileged processes. The untrusted-content clamd
daemon joins only the internal scanner network, mounts signatures read-only and
has no external DNS or egress. A separate updater joins only the outbound
signature-update network and owns the writable definition volume. Both run as
UID 100 with all capabilities dropped, no-new-privileges and read-only roots.
Health checks use the signed daily-database build timestamp, not filesystem
modification time, and require equality between the version loaded by clamd and
the version held on disk.

Use `scripts/start-local.ps1` as the guarded entry point. It rejects placeholder
values, shared database passwords, non-local origins and non-local environments.
It starts and waits for Compose, then `deploy-workflow-compose.ps1` inspects,
deploys when absent and attests the BPMN through the API container. Compose has
no optional profiles. Plain `docker compose up` starts the services but does not
perform workflow deployment or attestation, so request routing remains unready.
Compose explicitly forwards an allowlist of database-pool, session,
feature-flag and process settings rather than injecting every `.env` value. The
one-shot `migrator` applies Alembic and runtime grants before API startup.
Production deployments must likewise run migrations as an explicit release job
before application replicas are started or rolled forward.

The bootstrap creates a separate maintenance role and the migrator applies its
table-level grants, but a fresh Compose database does not currently grant that
role `CONNECT` on the application database. Retention apply and legal-hold apply
or release cannot run in the local stack until that provisioning defect is
fixed and retested. Preview, health and worker operations continue to use the
runtime identity. This limitation is not a reason to grant disposal permissions
to the API role.

Do not expose this topology on a shared host or use it in production. Production
requires private networking, OIDC, explicit Camunda authorisation, externally
managed PostgreSQL, encrypted and tested backups, restore exercises, supported
Kubernetes and Helm configuration, monitoring, and an appropriate Camunda
Self-Managed Enterprise licence. Compose volumes are persistence, not backups.

The repository currently has no application OIDC/bootstrap, S3/GCS product
runtime, Kubernetes/application Helm manifests, cloud infrastructure as code or
validated production topology. The Nginx configuration recognises local hosts
and proxies to the Compose API service. It is not a reusable production ingress.

Operational guides:

- [Local Docker](../docs/deployment/LOCAL_DOCKER.md)
- [Configuration reference](../docs/deployment/CONFIGURATION_REFERENCE.md)
- [Kubernetes target, explicitly unimplemented](../docs/deployment/KUBERNETES_TARGET.md)
- [Backup, restore and maintenance](../docs/operations/BACKUP_RESTORE_AND_MAINTENANCE.md)
