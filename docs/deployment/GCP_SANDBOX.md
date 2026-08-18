# Private Google Cloud synthetic sandbox

Status: documented evaluation pattern, not a production topology
Last reviewed: 18 August 2026

Complete the Linux sections of [Host setup](HOST_SETUP.md) and the local
[Docker topology](LOCAL_DOCKER.md) before creating cloud resources. This guide
adds the Google Cloud private-host and IAP controls only.

This procedure runs the local Compose topology on one private Compute Engine
Linux VM and accesses it through Identity-Aware Proxy (IAP). It permits only
synthetic, time-bounded evaluation. It is not a GKE or production design and
does not add OIDC, HA, managed data services, object storage or infrastructure
as code.

Use Google's [IAP TCP forwarding guide](https://cloud.google.com/iap/docs/using-tcp-forwarding)
as the platform authority. This procedure carries an SSH local-forward through
IAP because Mist deliberately listens on VM loopback rather than on the VM
network interface.

## 1. Prerequisites and approval

Obtain an approved sandbox project, billing budget, region/zone, owner, expiry
time and **synthetic-only** classification. Install and authenticate the Google
Cloud CLI on the operator workstation:

```powershell
gcloud version
gcloud auth login
gcloud config set project mist-sandbox-example
gcloud auth list
```

Use a recent supported Ubuntu LTS image, at least 8 vCPU, 32 GiB RAM and 100 GiB
encrypted persistent disk for the initial full-stack evaluation. Size changes
need measurement.

## 2. Create the private management path

1. Enable the Compute Engine and IAP APIs.
2. Create or select a VPC/subnet with Private Google Access where required.
3. Create a dedicated VM service account with no broad project role. Grant only
   permissions needed by approved host agents and monitoring.
4. Grant named operators `IAP-secured Tunnel User` and the minimum Compute/OS
   Login permissions. Avoid project-wide owner/editor.
5. Create an ingress firewall rule allowing TCP 22 only from Google's documented
   IAP TCP-forwarding range `35.235.240.0/20`, targeted to the sandbox VM tag or
   service account. Do not allow application ports.
6. Create the VM with no external IP, Shielded VM controls, OS Login, deletion
   protection according to the sandbox policy and owner/expiry/classification
   labels.
7. Provide controlled outbound package/image access through Cloud NAT or
   approved mirrors. IAP does not provide arbitrary outbound internet access.
8. Enable Cloud Audit Logs and the required host monitoring before evaluation.

Compose binds 5173, 8000, 8080, 9600 and 5432 to VM loopback. Do not weaken
those bindings or create public firewall rules.

## 3. Install host software

Connect through IAP:

```powershell
gcloud compute ssh mist-sandbox-vm `
  --zone europe-west2-a `
  --tunnel-through-iap
```

On the VM:

1. Apply approved OS updates.
2. Install Git and PowerShell 7.4 or later.
3. Install Docker Engine and Compose using Docker's supported
   [Linux instructions](https://docs.docker.com/engine/install/).
4. Configure the named operator to use Docker, recognising that Docker daemon
   access is root-equivalent.
5. Verify:

   ```bash
   docker version
   docker compose version
   pwsh --version
   git --version
   ```

## 4. Transfer and start the application

Use approved source or artefact transfer. `gcloud compute scp
--tunnel-through-iap` may be used for a reviewed archive, but never package a
`.env`, Git credential, local product or database dump unintentionally. Apply
the [immutable source procedure](HOST_SETUP.md#5-obtain-and-configure-the-source)
with the exact commit from the approved GCP sandbox release record.

```bash
approved_commit='<approved-40-character-release-commit>'
git clone <approved-repository-url> Mist-Service
git -C Mist-Service checkout --detach "$approved_commit"
test "$(git -C Mist-Service rev-parse HEAD)" = "$approved_commit"
cd Mist-Service
cp .env.example .env
chmod 600 .env
```

Configure unique secrets using the [configuration reference](CONFIGURATION_REFERENCE.md).
Keep `ENVIRONMENT=local`, demo users and synthetic content. This procedure does
not satisfy the `prod` boundary.

```bash
pwsh -File ./scripts/start-local.ps1
docker compose ps
curl -fsS http://127.0.0.1:8000/ready
```

The guarded helper deploys the BPMN and records availability through Compose.
Readiness must report every required check as `ok`. After opening the tunnel,
exercise a representative synthetic request through the application UI. Do not
run `scripts/smoke-camunda.ps1` against this stack because it deploys another,
unattested process-definition version.

## 5. Open a private browser tunnel

Run an SSH local-forwarding session over IAP on the operator workstation and
leave it active:

```powershell
gcloud compute ssh mist-sandbox-vm `
  --zone europe-west2-a `
  --tunnel-through-iap `
  -- -N -L 5173:127.0.0.1:5173
```

This forwards through the SSH service allowed from IAP to the application's
loopback-only port. It does not require a firewall rule or network listener on
5173. Open [http://localhost:5173](http://localhost:5173). The current origin
settings expect this exact port. If it is unavailable, use an approved alternate
origin and rebuild/reconfigure the evaluation rather than bypassing origin
checks.

Do not provide ordinary users with tunnels to PostgreSQL or Camunda. Diagnostic
tunnels require separate, time-bounded IAM authority.

## 6. Operate and observe

- Review IAP and Compute IAM membership before and after evaluation.
- Keep all requests, accounts and uploads synthetic.
- Use Cloud Logging/Monitoring for content-free host signals when the sandbox is
  persistent; the repository does not provide dashboard definitions.
- Inspect local service logs with `docker compose logs --tail 200 <service>`.
- Stop the VM outside approved hours and monitor budget alerts.
- Use checksum-verified database backups only when synthetic continuity is
  required. A persistent disk is not a backup.

## 7. Dispose

1. Close IAP tunnels and revoke temporary operator/evaluator roles.
2. Export only approved content-free assurance evidence.
3. Delete the VM, persistent disks, snapshots and reserved internal resources
   according to project policy.
4. Delete temporary firewall rules, service accounts, credentials and logs only
   when they are not shared and retention permits it.
5. Confirm project cost and resource inventory with the sandbox owner.

## Not supplied by this repository

There is no Terraform/Deployment Manager, Artifact Registry pipeline, external
HTTPS load balancer, Certificate Manager, Secret Manager integration, Cloud SQL,
GCS product adapter, GKE manifests or Google Cloud production implementation.
Those remain target-platform work governed by the
[Kubernetes target](KUBERNETES_TARGET.md) and [production gates](PRODUCTION_GATES.md).
