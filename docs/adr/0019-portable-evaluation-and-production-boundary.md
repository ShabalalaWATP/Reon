# ADR 0019: Separate portable evaluation from production deployment

Status: Accepted for the synthetic release candidate
Date: 8 August 2026

## Context

The repository supplies an executable Docker Compose topology with an
unauthenticated loopback Camunda endpoint, local product volume, local Nginx
assumptions and synthetic database accounts. It does not supply production OIDC,
cloud object storage, approved semantic scanning, infrastructure as code or a
validated high-availability topology. Publishing cloud-native instructions as
if those controls existed would be unsafe and operationally misleading.

## Decision

Docker Compose is the only implemented deployment topology. It may run on a
developer workstation or a private single Linux VM on AWS, Google Cloud or Azure
for time-bounded synthetic evaluation. All published ports stay on host
loopback. Operators reach the browser through SSM, IAP plus SSH forwarding, or
Azure Bastion plus SSH forwarding.

The web proxy joins a dedicated non-internal `front-door` network for its
loopback publication and the internal `service` network for API traffic. The
API and worker do not join `front-door`, so browser reachability does not grant
those runtimes a general outbound network path.

Kubernetes with managed PostgreSQL, a supported Camunda Helm deployment,
enterprise identity, private object storage, approved scanning and managed
observability is the production direction. It remains a target until versioned
platform assets and target-environment evidence exist. `ENVIRONMENT=prod` is a
validation boundary, not a deployment implementation or waiver.

Local workflow deployment records availability from inside the API container,
where the Compose database hostname resolves. Production release must use
separate migration, BPMN deployment and attestation jobs with distinct authority.

## Consequences

- Setup guides truthfully support Windows, macOS and Linux Docker plus private VM
  evaluation without opening application or dependency ports.
- Cloud-native production work cannot be completed through documentation alone.
- The production gate remains no-go while identity, Camunda authentication,
  product runtime, IaC, backup/recovery, edge security and owner acceptance are
  missing.
- Platform-specific implementation may later add child ADRs without weakening
  this distinction.

## Rejected alternatives

- **Expose Compose on a public VM:** rejected because local Camunda is
  deliberately unprotected and the topology has no production edge controls.
- **Call VM Compose production:** rejected because it lacks HA, managed identity,
  supported object storage and joined recovery.
- **Publish untested Helm or Terraform snippets:** rejected because plausible
  commands without owned assets and validation create false assurance.
- **Use a scale-to-zero function/container service unchanged:** rejected because
  the independently deployed maintenance worker requires continuously allocated
  execution and a fresh durable heartbeat. ADR 0020 supersedes the earlier
  in-process-loop implementation detail without changing this conclusion.
