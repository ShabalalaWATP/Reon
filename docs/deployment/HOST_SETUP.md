# Workstation and Linux host setup

Status: current setup authority for the executable Docker Compose topology
Last reviewed: 18 August 2026

This guide prepares Windows, macOS and Linux hosts for Mist Service. It is the
common prerequisite for local use and for the private AWS and Google Cloud
and Azure synthetic-evaluation guides. The repository supplies one executable
topology: Docker Compose. It is suitable for development and synthetic
evaluation only.

## 1. Choose a host path

| Host | Recommended runtime | Shell used by repository scripts |
|---|---|---|
| Windows 11 | Docker Desktop with WSL 2 backend | PowerShell 7.4+ |
| MacBook, Apple silicon or Intel | Docker Desktop for the correct architecture | PowerShell 7.4+ |
| Linux workstation or private VM | Docker Engine with Compose v2 plugin | PowerShell 7.4+ |

Allow at least 8 logical CPU cores, 16 GiB RAM and 40 GiB free disk for a local
developer run. A full private-VM evaluation is more comfortable with 8 vCPU,
32 GiB RAM and 100 GiB disk. These are starting points, not measured production
capacity.

All platforms also need:

- Git 2.45 or later;
- Docker Compose v2, invoked as `docker compose`;
- PowerShell 7.4 or later, invoked as `pwsh`;
- a current Chromium browser; and
- optional Node.js 22+, pnpm 11.21.0, Python 3.12+ and `uv` when developing from
  source outside containers. Repository scripts also require the `corepack`
  command; install an approved Corepack package when the Node distribution does
  not include it.

## 2. Windows 11

1. Enable hardware virtualisation in firmware and install WSL 2.
2. Install Docker Desktop and select the WSL 2 backend.
3. Install PowerShell 7 and Git for Windows.
4. Keep the repository inside the Windows filesystem for ordinary PowerShell
   use, or entirely inside one WSL distribution for Linux-shell use. Do not
   split the repository and Docker bind mounts across both environments.
5. In PowerShell, verify:

   ```powershell
   git --version
   pwsh --version
   docker version
   docker compose version
   ```

6. Configure Docker Desktop with enough CPU, memory and disk. Corporate VPN,
   proxy and endpoint controls must permit the approved container registries.

If Docker reports that the daemon is unavailable, start Docker Desktop and wait
until `docker version` shows both Client and Server. If a corporate proxy is in
use, configure it in Docker Desktop rather than putting credentials in `.env`.

## 3. macOS on a MacBook

1. Confirm the processor architecture with `uname -m`: `arm64` is Apple silicon
   and `x86_64` is Intel.
2. Install the matching Docker Desktop package, PowerShell 7 and Git. Homebrew is
   one supported package-management option, but follow organisational software
   approval rules.
3. Verify in Terminal:

   ```bash
   uname -m
   git --version
   pwsh --version
   docker version
   docker compose version
   ```

4. Give Docker Desktop adequate resources and repository-directory access.
5. Keep the default case-insensitive filesystem limitation in mind. CI and Linux
   containers are case-sensitive, so imports must match file names exactly.

The supplied multi-platform images support the local architecture selected by
Docker. Do not force `linux/amd64` on Apple silicon unless a documented upstream
image limitation requires emulation, because it is slower and can hide platform
defects.

## 4. Linux workstation or private VM

Use a currently supported distribution. The cloud sandbox guides use a recent
Ubuntu LTS as the reference host.

1. Apply operating-system updates through the approved package source.
2. Install Git and PowerShell 7.4+.
3. Install Docker Engine and the Compose plugin from Docker's supported
   distribution repository. Do not pipe an unaudited convenience script into a
   privileged shell.
4. Enable and start Docker where restart recovery is required.
5. Decide who may access the Docker socket. Membership of the Docker group is
   effectively root-level host authority.
6. Verify:

   ```bash
   git --version
   pwsh --version
   docker version
   docker compose version
   ```

For a shared VM, keep the checkout, `.env`, backups and product volume accessible
only to the named operator. Use `chmod 600 .env` after creating the environment
file. Do not publish application or dependency ports on the VM network. The
supplied Compose file binds them to loopback.

## 5. Obtain and configure the source

Clone from the approved repository endpoint and detach at the exact 40-character
commit recorded in the approved release evidence. Never execute a mutable
default branch, tag or archive by name alone. Never put a personal access token
in the clone URL, shell history or `.env`.

```powershell
$approvedCommit = '<approved-40-character-release-commit>'
git clone <approved-repository-url> Mist-Service
git -C Mist-Service checkout --detach $approvedCommit
if ((git -C Mist-Service rev-parse HEAD).Trim() -ne $approvedCommit) {
    throw 'The checkout does not match the approved release commit.'
}
Set-Location Mist-Service
Copy-Item .env.example .env
```

On macOS or Linux, the final two commands can be:

```bash
approved_commit='<approved-40-character-release-commit>'
git -C Mist-Service checkout --detach "$approved_commit"
test "$(git -C Mist-Service rev-parse HEAD)" = "$approved_commit"
cd Mist-Service
cp .env.example .env
chmod 600 .env
```

Where the release authority requires signed commits, run `git verify-commit`
against that same commit and retain the successful identity result. A commit ID
still requires approval through a trusted release record; it is not approval by
itself.

Replace every placeholder secret in `.env`, including separate maintenance and
security-pseudonym credentials. Keep `ENVIRONMENT=local` for this topology.
Setting `ENVIRONMENT=prod` is not a production deployment shortcut and will
deliberately fail with the demonstration feature set because no approved
managed-product runtime is injected. Use the
[configuration reference](CONFIGURATION_REFERENCE.md) for every setting.

## 6. Start and prove the complete application

From the repository root:

```powershell
pwsh -File ./scripts/start-local.ps1
docker compose ps
```

The guarded start script builds the application, starts PostgreSQL, Camunda,
ClamAV, API, worker and web containers, applies current migrations and deploys
the compatible BPMN definition. It does not silently convert an incompatible
database or workflow deployment.

Check readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

On macOS or Linux, `curl -fsS http://127.0.0.1:8000/ready` is equivalent. Every
required readiness check must be `ok`. Then open
[http://127.0.0.1:5173](http://127.0.0.1:5173).

Qualify workflow through the integrated synthetic application journey documented
in [Local Docker](LOCAL_DOCKER.md). Do not run the Camunda-only smoke against an
attested application stack because it deploys another process-definition
version.

## 7. Develop from source

Install Node.js 22+, Corepack, pnpm 11.21.0 and `uv`, then run:

```powershell
corepack enable
pnpm install --frozen-lockfile
uv sync --directory apps/api --all-groups --frozen
```

The supported hybrid loop is documented in
[Local source development](LOCAL_SOURCE_DEVELOPMENT.md). The container topology
remains the integration authority because it includes the real PostgreSQL,
Camunda and ClamAV boundaries.

## 8. Stop, restart and update

Stop application containers without deleting data:

```powershell
docker compose stop
```

Resume them through the guarded start script. Before updating source, take an
approved backup when synthetic continuity matters, inspect release notes and
then use a non-destructive Git update appropriate to the current branch. Do not
delete volumes to solve a migration or readiness error.

To remove an evaluation permanently, first confirm the exact Compose project and
follow the backup and disposal policy. Volume deletion destroys the application
database, Camunda database and managed product files.

## 9. Common failures

| Symptom | Check | Safe response |
|---|---|---|
| Docker daemon unavailable | `docker version` | Start the approved Docker runtime; do not reinstall blindly. |
| Port already in use | `docker compose ps` and host listener inventory | Stop the known conflicting process or use an approved topology change. |
| API says page unavailable intermittently | `docker compose ps`, API and worker logs, `/ready` | Treat readiness failure as the cause; do not repeatedly reload until it happens to pass. |
| Camunda not ready | Camunda health and worker logs | Wait for bounded startup or resolve the reported compatibility/dependency failure. |
| Product upload unavailable | ClamAV health, API logs and storage permissions | Restore scanning and storage; never bypass malware checks. |
| Browser session behaves unexpectedly | Exact origin, cookies and active context | Use `127.0.0.1:5173`, sign out, and inspect API diagnostics without exposing session data. |
| Database migration error | Migration job output and current Alembic revision | Stop and diagnose. Never edit the schema manually or delete the database as a first response. |

Use `docker compose logs --tail 200 <service>` for bounded diagnostics. Do not
paste request content, passwords, cookies, tokens or database dumps into issue
trackers.

## 10. Next deployment choice

- For a private, time-bounded AWS evaluation, continue with
  [Private AWS synthetic sandbox](AWS_SANDBOX.md).
- For a private, time-bounded Google Cloud evaluation, continue with
  [Private Google Cloud synthetic sandbox](GCP_SANDBOX.md).
- For production architecture, read the [Kubernetes target](KUBERNETES_TARGET.md)
  and [production gates](PRODUCTION_GATES.md). The repository does not yet
  contain production infrastructure or an approved production data path.
