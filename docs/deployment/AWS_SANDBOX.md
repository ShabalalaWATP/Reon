# Private AWS synthetic sandbox

Status: documented evaluation pattern, not a production topology
Last reviewed: 18 August 2026

Complete the Linux sections of [Host setup](HOST_SETUP.md) and the local
[Docker topology](LOCAL_DOCKER.md) before creating cloud resources. This guide
adds the AWS private-host and operator-tunnel controls only.

This procedure runs the unchanged local Compose stack on one private EC2 Linux
instance and reaches it through AWS Systems Manager Session Manager port
forwarding. It is suitable only for synthetic, time-bounded evaluation. It does
not provide HA, OIDC, managed PostgreSQL, production Camunda, object storage,
infrastructure as code or accepted monitoring/backup controls.

AWS documents that Session Manager avoids inbound management ports. See
[Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
and its [port-forwarding procedure](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html).
Port-forwarded traffic contents are not captured in Session Manager session
logs, so rely on IAM/CloudTrail session events and application audit, not tunnel
payload logging.

## 1. Prerequisites and approval

Obtain an approved sandbox account, budget, region, owner, expiry time and data
classification of **synthetic only**. The operator workstation needs AWS CLI v2
and the Session Manager plugin. Verify:

```powershell
aws --version
session-manager-plugin
aws sts get-caller-identity
```

Use a recent supported Ubuntu LTS or Amazon Linux image. Allow at least 8 vCPU,
32 GiB RAM and 100 GiB encrypted gp3 disk for a comfortable full-stack
evaluation. Validate the actual load before reducing it.

## 2. Create the private management path

1. Create or select a VPC with private subnets and no direct route from the
   internet to the instance.
2. Provide controlled outbound access for OS packages, Git and pinned container
   images, or use approved mirrors. A NAT gateway is one option; Systems Manager
   VPC endpoints do not replace every image/package endpoint.
3. Create an EC2 IAM role with the minimum Systems Manager managed-node
   permissions. AWS's `AmazonSSMManagedInstanceCore` policy is the usual sandbox
   starting point; narrow further where the platform supports it.
4. Create a security group with **no inbound rules**. Limit outbound traffic to
   approved destinations and VPC endpoints.
5. Launch the encrypted instance without a public IPv4 address and attach the
   instance role and security group.
6. Require IMDSv2, encrypted EBS and account-level CloudTrail. Apply owner,
   classification, expiry and cost-centre tags.
7. Confirm the instance appears as an online Systems Manager managed node.

Do not open 5173, 8000, 8080, 9600, 5432 or SSH to the internet. Compose already
binds application ports to the instance loopback interface.

## 3. Install host software

Start an interactive Session Manager shell:

```powershell
aws ssm start-session --target i-0123456789abcdef0
```

On the instance:

1. Apply approved OS updates.
2. Install Git and PowerShell 7.4 or later.
3. Install Docker Engine and the Compose plugin using Docker's exact
   [distribution instructions](https://docs.docker.com/engine/install/), not an
   unaudited convenience script.
4. Configure the evaluation operator to use Docker. Treat Docker daemon access
   as root-equivalent.
5. Verify:

   ```bash
   docker version
   docker compose version
   pwsh --version
   git --version
   ```

6. Enable Docker at boot only if the sandbox owner requires restart recovery.

## 4. Transfer and configure Mist

Use an approved private Git endpoint or controlled artefact transfer. Apply the
[immutable source procedure](HOST_SETUP.md#5-obtain-and-configure-the-source)
with the exact commit from the approved AWS sandbox release record. Do not put a
personal access token in shell history, user data or `.env`.

```bash
approved_commit='<approved-40-character-release-commit>'
git clone <approved-repository-url> Mist-Service
git -C Mist-Service checkout --detach "$approved_commit"
test "$(git -C Mist-Service rev-parse HEAD)" = "$approved_commit"
cd Mist-Service
cp .env.example .env
chmod 600 .env
```

Edit `.env` with unique sandbox secrets. Retain `ENVIRONMENT=local`, loopback
origins, demo users and synthetic data because this is deliberately the local
topology. Setting `prod` would fail on missing product runtime and would not make
this production-worthy. Follow the [configuration reference](CONFIGURATION_REFERENCE.md).

Start and attest:

```bash
pwsh -File ./scripts/start-local.ps1
docker compose ps
curl -fsS http://127.0.0.1:8000/ready
```

Readiness must be `ready`. Exercise a representative synthetic request through
the application UI after opening the tunnel below. Do not run
`scripts/smoke-camunda.ps1` against this stack: it deploys a new, unattested
process-definition version and is reserved for disposable standalone Camunda
testing.

## 5. Open a private browser tunnel

From the operator workstation, keep this command running:

```powershell
aws ssm start-session `
  --target i-0123456789abcdef0 `
  --document-name AWS-StartPortForwardingSession `
  --parameters '{"portNumber":["5173"],"localPortNumber":["5173"]}'
```

If local port 5173 is occupied, choose another `localPortNumber` and browse to
that port. Note that the current web origin/cookie policy expects
`http://localhost:5173`; changing the local tunnel port also requires an approved
origin configuration and image/topology review.

Open [http://localhost:5173](http://localhost:5173). Do not tunnel Camunda or
PostgreSQL to ordinary evaluators. Give operators a separate time-bounded IAM
permission when diagnostic API access is justified.

## 6. Operate the sandbox

- Limit IAM access to named evaluators and review it at the end of each session.
- Keep repository data synthetic and inspect uploads before use.
- Send content-free host/container health to the approved account monitoring
  service if the evaluation lasts more than a single session.
- Use `docker compose logs --tail 200 <service>` inside the SSM session. Never
  paste request content or secrets into tickets.
- Stop the instance outside evaluation hours. Confirm whether stop/start meets
  the agreed recovery expectations before relying on it.
- Compose volumes are not backups. Use the repository backup procedure if test
  continuity matters, then store artefacts in an approved encrypted location.

## 7. Dispose

1. Close all SSM sessions and revoke temporary evaluator IAM assignments.
2. Export only approved content-free evidence.
3. Terminate the EC2 instance and delete its attached EBS volumes and snapshots
   according to the sandbox disposal policy.
4. Remove temporary secrets, repository credentials, log groups and security
   groups when no longer shared.
5. Confirm deletion and cost cessation with the named sandbox owner.

Disposal is a cloud-owner action and must not be inferred from stopping Compose.

## Not supplied by this repository

There is no CloudFormation/CDK/Terraform, ECR pipeline, ALB, ACM, Route 53,
Secrets Manager injection, RDS, S3 product adapter, central observability or AWS
production reference implementation. Design those only through the
[Kubernetes target](KUBERNETES_TARGET.md) and production gates.
