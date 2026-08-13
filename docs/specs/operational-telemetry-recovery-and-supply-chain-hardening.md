# Operational telemetry, recovery and supply-chain hardening

## Status and scope

Status: implementation approved on 13 August 2026.

This change covers the local container build boundary, content-minimised HTTP
telemetry, PostgreSQL backup and restore tooling, and the local Camunda network
topology. It does not turn the local Compose stack into a production template.

## Required outcomes

- Uvicorn and Nginx raw access logs are disabled. The API emits one JSON event
  through `istari_service.access`, using the matched route template or the fixed
  value `unmatched`, never the request target or query string.
- Built runtime images are exercised by canaries after build. The live canary
  starts the built web and API images on a temporary internal network, sends an
  unmatched request containing distinct path, query and User-Agent markers, and
  proves those markers are absent from both containers' logs while the API emits
  the fixed `unmatched` route event. CI scans and creates SBOMs for deployed
  images, dependency-bearing builder stages and security-tool images.
- Node build stages use a supported digest-pinned Node 24 LTS image. Every custom
  Dockerfile frontend directive is digest-pinned.
- Remote backup and restore URLs use `sslmode=verify-full` and an existing CA
  bundle whose canonical path exactly matches the operator-approved path. Only
  `localhost`, `127.0.0.1` and `[::1]` receive the local plaintext exception.
- A backup manifest authenticates its checksum, filename and creation timestamp
  with HMAC-SHA256 and a separately supplied key of at least 256 bits. Restore
  fails before database access when authentication or checksum verification fails.
- The Camunda data initialiser has no network and a read-only container root. The
  runtime joins only internal data and workflow networks, separate from the web
  proxy network.
- The web proxy alone joins a non-internal front-door network so its loopback
  port remains reachable. API traffic stays on the separate internal service
  network, which the worker and API use without joining the front door.

## Acceptance criteria

1. Telemetry tests prove route-template-only JSON events and unmatched-path
   minimisation, while container contracts prove both raw access logs are off.
2. Pester tests accept only the exact local URL exceptions and reject weak remote
   TLS, unapproved trust paths, dump tampering and coordinated dump-plus-manifest
   tampering without the integrity key.
3. Compose validation, built-image canaries, Trivy inventory and CycloneDX
   inventory cover every declared runtime, builder and tool image.
4. No credential, CA bundle or integrity key is committed or emitted as evidence.
5. CI runs the Pester recovery policy suite on the pinned runner image.
