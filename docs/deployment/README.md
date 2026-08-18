# Deployment guide

Last reviewed: 18 August 2026

## Choose the correct path

| Goal | Use | Data allowed |
|---|---|---|
| Prepare Windows, a MacBook or Linux | [Host setup](HOST_SETUP.md) | No application data |
| Run the complete application on a workstation | [Local Docker](LOCAL_DOCKER.md) | Synthetic only |
| Develop API or web code with dependencies available | [Local source development](LOCAL_SOURCE_DEVELOPMENT.md) | Synthetic only |
| Give a private AWS evaluation to a bounded group | [AWS sandbox](AWS_SANDBOX.md) | Synthetic only |
| Give a private Google Cloud evaluation to a bounded group | [GCP sandbox](GCP_SANDBOX.md) | Synthetic only |
| Give a private Azure evaluation to a bounded group | [Azure sandbox](AZURE_SANDBOX.md) | Synthetic only |
| Plan a connected production platform | [Kubernetes target](KUBERNETES_TARGET.md) | None until all gates pass |

Before changing an environment, read the [configuration reference](CONFIGURATION_REFERENCE.md).
Before promoting a candidate, follow the [release runbook](RELEASE_RUNBOOK.md)
and [production gates](PRODUCTION_GATES.md).

## Current support statement

Docker Compose is the only executable topology supplied by this repository. It
is for development and synthetic evaluation. Private AWS EC2, GCP Compute
Engine and Azure VM hosts can run that same loopback-bound Compose topology
behind SSM, IAP or Bastion/SSH tunnels. These are not production patterns.

The same current application runs in each supported host path: React/Nginx,
FastAPI, the independent worker, PostgreSQL, Camunda and ClamAV. AWS, Google
Cloud and Azure instructions do not replace PostgreSQL with a different
application database or introduce a cloud-native product store. They host the
unchanged synthetic topology on one private Linux VM.

The production direction is Kubernetes, an external managed PostgreSQL service,
a supported Camunda 8.9 Helm deployment, an enterprise identity provider,
private product object storage and managed observability. It is a design target,
not implemented infrastructure. There are no Kubernetes manifests, application
Helm chart, Terraform modules or validated cloud topology in the repository.

## Hard blockers

- Application OIDC and first-user/role bootstrap are not implemented.
- The Camunda client supports only `NONE` and `BASIC`; local Camunda is
  deliberately unprotected on host loopback.
- Production managed products cannot start without an injected approved runtime;
  no S3, GCS or Azure Blob adapter is supplied.
- The web image contains local Nginx host and upstream assumptions.
- There is no infrastructure as code, production secret integration, HA design
  evidence, capacity test or multi-store disaster-recovery rehearsal.
- Fresh Compose provisioning omits database `CONNECT` for the maintenance role,
  so retention apply and legal-hold apply/release are not current local evidence.
- The restore helper currently cannot pass one database URL through both its
  libpq tools and async Python verifier, so no current-head restore rehearsal can
  be claimed from that command.

These blockers cannot be removed by setting `ENVIRONMENT=prod`.

## Official platform references

- [Docker Desktop](https://docs.docker.com/desktop/) and
  [Docker Engine installation](https://docs.docker.com/engine/install/)
- [AWS Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [GCP IAP TCP forwarding](https://cloud.google.com/iap/docs/using-tcp-forwarding)
- [Azure Bastion tunnelling](https://learn.microsoft.com/azure/bastion/connect-vm-native-client-windows)
- [Camunda 8.9 Self-Managed deployment](https://docs.camunda.io/docs/self-managed/deployment/)
- [Camunda production Helm installation](https://docs.camunda.io/docs/self-managed/deployment/helm/install/production/)
