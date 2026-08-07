# Local infrastructure boundary

This Compose topology is for local development and evaluation only. It binds
PostgreSQL, the Camunda API, the product API and the web application to the host
loopback interface. The Camunda V2 API is intentionally unprotected locally.

PostgreSQL uses a bootstrap superuser only to initialise two separately owned
databases. The application role cannot own or migrate Camunda storage, and the
Camunda role cannot own or migrate product data. Named volumes retain PostgreSQL
and Camunda engine state across normal container recreation.

Use `scripts/start-local.ps1` as the guarded entry point. It rejects placeholder
values, shared database passwords, non-local origins and non-local environments.
The API's automatic migration on start is suitable only for this single-replica
local topology. Production deployments must run migrations as an explicit,
one-shot release job before application replicas are started or rolled forward.

Do not expose this topology on a shared host or use it in production. Production
requires private networking, OIDC, explicit Camunda authorisation, externally
managed PostgreSQL, encrypted and tested backups, restore exercises, supported
Kubernetes and Helm configuration, monitoring, and an appropriate Camunda
Self-Managed Enterprise licence. Compose volumes are persistence, not backups.
