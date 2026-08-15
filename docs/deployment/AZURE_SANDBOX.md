# Private Azure synthetic sandbox

Status: documented evaluation pattern, not a production topology

This procedure runs the unchanged local Compose topology on one private Azure
Linux VM. Azure Bastion carries SSH to the VM, then SSH local forwarding reaches
the application's loopback-only web port. Only synthetic, time-bounded
evaluation is permitted.

Microsoft documents [native-client Bastion connections](https://learn.microsoft.com/en-us/azure/bastion/native-client)
and the [Bastion tunnel command](https://learn.microsoft.com/en-us/azure/bastion/connect-vm-native-client-windows).
The Bastion tunnel terminates on SSH port 22, not the web application.

## 1. Prepare the subscription and workstation

1. Obtain an approved sandbox subscription, budget, region, owner, expiry date
   and synthetic-only classification.
2. Install Azure CLI, OpenSSH, Git and an organisation-approved SSH key.
3. Sign in and select the exact subscription:

   ```powershell
   az login
   az account set --subscription <subscription-id>
   az account show --query "{name:name,id:id}" --output table
   ```

4. Record the resource-group and resource names. Do not paste secrets into CLI
   arguments, deployment output or cloud-init.

## 2. Create the private host and management path

1. Create a resource group, virtual network, VM subnet and `AzureBastionSubnet`
   under the organisation's network policy.
2. Deploy Azure Bastion with native-client support. A private-only Bastion tier
   may be required by policy.
3. Create a supported Ubuntu LTS VM with no public IP, encrypted managed disk,
   at least 8 vCPU, 32 GiB RAM and 100 GiB disk for the initial full-stack
   evaluation. Reduce only after measuring the workload.
4. Permit SSH from the Bastion subnet to the VM. Do not add inbound rules for
   5173, 8000, 8080, 9600 or 5432.
5. Grant named operators the minimum VM, NIC and Bastion reader/login roles.
   Avoid subscription-wide Owner or Contributor.
6. Provide controlled outbound access for OS packages, Git and pinned images.
7. Enable activity logs, VM monitoring, budget alerts and owner/expiry tags.

## 3. Open SSH and install the stack

Open a local tunnel to the VM's SSH service:

```powershell
$vmId = az vm show --resource-group mist-sandbox-rg `
  --name mist-sandbox-vm --query id --output tsv
az network bastion tunnel --name mist-sandbox-bastion `
  --resource-group mist-sandbox-rg `
  --target-resource-id $vmId --resource-port 22 --port 50022
```

Leave that command running. In a second terminal:

```powershell
ssh -p 50022 <vm-user>@127.0.0.1
```

On the VM, apply approved updates and install Git, PowerShell 7.4, Docker Engine
and the Compose plugin using Docker's supported Linux instructions. Docker
daemon access is root-equivalent.

```bash
docker version
docker compose version
pwsh --version
git --version
```

## 4. Configure and start Mist

```bash
git clone <approved-repository-url> Mist-Service
cd Mist-Service
cp .env.example .env
chmod 600 .env
```

Replace every placeholder with a unique sandbox secret. Retain local mode, demo
users, loopback origins and synthetic content. Follow the
[configuration reference](CONFIGURATION_REFERENCE.md), then run:

```bash
pwsh -File ./scripts/start-local.ps1
docker compose ps
curl -fsS http://127.0.0.1:8000/ready
pwsh -File ./scripts/smoke-camunda.ps1
```

## 5. Forward the browser through SSH

Reuse the Bastion-to-SSH tunnel from step 3. In another local terminal, create
an SSH connection whose only purpose is browser forwarding:

```powershell
ssh -p 50022 -N -L 5173:127.0.0.1:5173 <vm-user>@127.0.0.1
```

Open [http://localhost:5173](http://localhost:5173). This keeps port 5173 bound
to VM loopback and does not expose it through an NSG. Do not forward Camunda or
PostgreSQL to ordinary evaluators.

## 6. Operate and dispose

- Keep all requests and uploads synthetic.
- Review Bastion, VM and role access before and after each evaluation window.
- Stop or deallocate the VM outside approved hours.
- Treat managed disks as persistence, not backups. Use the repository's
  checksum-verified backup procedure if synthetic continuity matters.
- At expiry, close tunnels, revoke temporary roles, export only approved
  content-free evidence, and delete the VM, disks, snapshots and unshared
  network resources with cloud-owner approval.

There is no Bicep/Terraform, ACR pipeline, Key Vault injection, managed
PostgreSQL, object-storage adapter, AKS manifest or Azure production reference
implementation in this repository.
