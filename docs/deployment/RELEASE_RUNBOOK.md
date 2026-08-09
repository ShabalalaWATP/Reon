# Release runbook

Status: executable local candidate procedure plus production-target controls

This runbook releases a reviewed candidate. It does not authorise real data or
convert the local Compose topology into production. Use a named operator and
record timestamps, commit SHA, image digests, migration revision, BPMN checksum,
test results and approvals without recording secrets or request content.

## 1. Qualify the source candidate

1. Start from a clean reviewed branch and record `git rev-parse HEAD`.
2. Install locked dependencies:

   ```powershell
   pnpm install --frozen-lockfile
   uv sync --project apps/api --all-groups --frozen
   ```

3. Run repository and application gates:

   ```powershell
   pnpm check
   uv run --directory apps/api ruff format --check .
   uv run --directory apps/api ruff check .
   uv run --directory apps/api mypy
   uv run --directory apps/api bandit -c pyproject.toml -r src alembic
   uv run --directory apps/api pip-audit
   uv run --directory apps/api pytest
   pnpm --filter @istari-service/web test
   pnpm --filter @istari-service/web build
   pnpm --filter @istari-service/web contract:openapi
   pnpm smoke-contract
   ```

4. Resolve failures. Do not lower coverage or suppress a vulnerability merely to
   pass the candidate.
5. Validate the BPMN and migrations, including empty-database and previous-head
   upgrade paths.
6. Build immutable images, scan API, web, PostgreSQL, Camunda and ClamAV images,
   retain their CycloneDX SBOMs and record digests. Current CI supplies those
   local candidate controls. Production qualification remains blocked until
   signing, provenance, admission verification and applicable IaC scanning are
   implemented for the selected platform.

## 2. Prepare the change

1. Confirm the environment is supported in the
   [deployment matrix](README.md). For production, every
   [production gate](PRODUCTION_GATES.md) must have evidence and acceptance.
2. Identify the migration owner, workflow deployer, application operator,
   rollback authority and incident contact. Keep duties separate where required.
3. Take and verify the required backups. Confirm RPO/RTO and the restoration
   candidate, not merely backup job success.
4. Compare current and target Alembic revisions, BPMN checksum, configuration
   version and feature flags.
5. Review backwards compatibility and the rollback boundary. A database or
   workflow change that is not backwards compatible requires a specific restore
   or roll-forward plan.
6. Announce the maintenance window through the approved organisational process.

## 3. Release the local Docker candidate

1. Copy and validate `.env` as described in [Local Docker](LOCAL_DOCKER.md).
2. Pull or build the exact candidate.
3. Start database dependencies and the one-shot migrator through the guarded
   entry point:

   ```powershell
   pwsh -File ./scripts/start-local.ps1
   ```

4. The script validates and deploys `workflow/service-request.bpmn`, then runs
   attestation inside the API container so Compose DNS is valid.
5. Verify containers, liveness and readiness:

   ```powershell
   docker compose ps
   Invoke-RestMethod http://127.0.0.1:8000/health
   Invoke-RestMethod http://127.0.0.1:8000/ready
   ```

6. Run `pwsh -File ./scripts/smoke-camunda.ps1` and the representative browser
   journey. Confirm login, request submission, routing, clarification, product
   release/download and feedback as applicable to enabled features.
7. Record content-free evidence and the exact candidate identity.

## 4. Target Kubernetes release order

This sequence is not executable until platform assets exist:

1. Verify signed image and infrastructure artefact identities.
2. Quiesce incompatible writes when the migration plan requires it.
3. Run the database migration/permission Job once and verify the head revision.
4. Deploy BPMN through the controlled workflow Job.
5. Run workflow attestation against application PostgreSQL.
6. Roll the API and maintenance worker with readiness gates.
7. Roll the web application and ingress configuration.
8. Run target health, security, workflow and browser checks.
9. Re-enable traffic only after readiness and smoke evidence is accepted.
10. Monitor error, latency, outbox age, reconciliation, login, scanner and
    database-capacity signals through the agreed observation window.

## 5. Failure and rollback

- If migration fails, keep application traffic closed. Capture content-free
  diagnostics and follow the migration-specific recovery plan.
- If BPMN deployment or attestation fails, do not start new requests. Existing
  requests remain pinned to their recorded definition.
- If readiness fails, do not override the probe. Inspect the named dependency,
  maintenance health and configuration seal.
- Roll back stateless images only when the schema and workflow remain compatible.
- Restore data only under incident/change authority. Follow the joined recovery
  order in the continuity runbook, then reconcile before reopening ingress.
- Record the outcome, user impact, candidate identity and follow-up owner.

## 6. Close the release

1. Obtain the required technical, security, product and operational acceptance.
2. Update the implementation plan, development story, evidence ledger and gap
   register only with facts proved by this candidate.
3. Retain logs and artefacts under the approved content and retention policy.
4. Remove temporary privileges and revoke unused release credentials.
