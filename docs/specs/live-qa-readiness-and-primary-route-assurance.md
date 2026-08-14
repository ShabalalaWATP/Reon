# Live QA readiness and primary-route assurance

## Purpose

The rebuilt local QA stack must be ready by its own `/ready` contract, not only
live by `/health`. Operators also need maintained application-level journeys for
the primary SSG route and a configured alternative route.

## Requirements

1. Local workflow deployment records an auditable checksum-bound availability
   attestation before new requests are accepted.
2. The guarded startup path uses the internal Compose workflow network and does
   not depend on a host-published, unauthenticated Camunda port.
3. Startup reuses one exact active BPMN match, deploys only when no definition
   exists, and stops without mutation on conflicts or unattested existing state.
4. A rebuilt QA stack reports database, workflow, configuration and maintenance
   checks as `ok`.
5. The primary journey exercises Customer, CRIOC, JOCK, ACSA-B Ops, SSG Team,
   Ben Doak as Lead Analyst, Manager review, QC and Customer download.
6. The alternative journey exercises Customer, CRIOC, SYGOC, Nimbus Ops,
   Beacon Team, Manager review, QC and Customer download.
7. Journey scripts use the current public request and assignment schemas.
8. Local passwords remain environment inputs and are never written to reports.

## Acceptance

- The API container's `/health` and `/ready` endpoints return HTTP 200 in the
  rebuilt QA stack. The browser proxy exposes only `/api/*`, by design.
- Re-running guarded deployment reuses the exact active workflow without
  creating another process version.
- Both application journeys complete and verify the downloaded service product.
- The customer profile route renders without an application crash.
- Repository checks, backend/frontend tests and security gates pass.
