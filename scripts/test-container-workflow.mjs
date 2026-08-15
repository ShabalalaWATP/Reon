import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const workflowPath = join(
  scriptDirectory,
  "..",
  ".github",
  "workflows",
  "container-validation.yml",
);
const workflow = await readFile(workflowPath, "utf8");
const repositoryRoot = join(scriptDirectory, "..");
const compose = await readFile(join(repositoryRoot, "docker-compose.yml"), "utf8");
const postgresDockerfile = await readFile(
  join(repositoryRoot, "infra", "postgres", "Dockerfile"),
  "utf8",
);
const canary = await readFile(
  join(repositoryRoot, "scripts", "canary-built-containers.sh"),
  "utf8",
);
const normalisedWorkflow = workflow.replace(/\s+/gu, " ");
const expectedImages = [
  "mist-service-local-api",
  "mist-service-local-web",
  "mist/postgres-local:17.10-pgvector0.8.1-alpine3.23",
  "mist/camunda-local:8.9.14",
  "mist/clamav-local:1.5.3",
  "mist-build-api:ci",
  "mist-build-web:ci",
  "mist-build-postgres:ci",
  "mist-tool-actionlint:ci",
  "mist-tool-gitleaks:ci",
  "mist-tool-trufflehog:ci",
  "mist-tool-trufflehog-gate:ci",
  "mist-tool-uv:ci",
  "mist-tool-dockerfile-frontend:ci",
];

for (const required of [
  "push:",
  "pull_request:",
  "schedule:",
  "name: Container and Compose validation",
  "docker compose build api web postgres orchestration clamav",
  "name: Exercise built-container canaries",
  "sh scripts/canary-built-containers.sh",
  "python /assurance/postgres_migration_roundtrip.py",
  "alembic downgrade -1",
  "alembic upgrade head",
  "alembic check",
  "name: Generate CycloneDX image SBOMs",
  "api=mist-service-local-api",
  "web=mist-service-local-web",
  "postgres=mist/postgres-local:17.10-pgvector0.8.1-alpine3.23",
  "camunda=mist/camunda-local:8.9.14",
  "clamav=mist/clamav-local:1.5.3",
  "api-builder=mist-build-api:ci",
  "web-builder=mist-build-web:ci",
  "postgres-builder=mist-build-postgres:ci",
  "actionlint-tool=mist-tool-actionlint:ci",
  "gitleaks-tool=mist-tool-gitleaks:ci",
  "trufflehog-tool=mist-tool-trufflehog:ci",
  "trufflehog-gate-tool=mist-tool-trufflehog-gate:ci",
  "uv-tool=mist-tool-uv:ci",
  "dockerfile-frontend-tool=mist-tool-dockerfile-frontend:ci",
  "if: always()",
  "docker compose down --volumes --remove-orphans",
]) {
  assert.ok(
    normalisedWorkflow.includes(required),
    `container workflow is missing: ${required}`,
  );
}

const trivyImages = [...workflow.matchAll(
  /uses: aquasecurity\/trivy-action@[^\r\n]+[\s\S]*?image-ref: ([^\r\n]+)/gu,
)].map((match) => match[1].trim());
assert.deepEqual(
  [...trivyImages].sort(),
  [...expectedImages].sort(),
  "Trivy gates must cover each deployed image exactly once",
);

const buildMatch = workflow.match(/docker compose\s+build ([^\r\n]+)/u);
assert.ok(buildMatch, "container build service list is missing");
assert.deepEqual(
  buildMatch[1].trim().split(/\s+/u).sort(),
  ["api", "web", "postgres", "orchestration", "clamav"].sort(),
  "container build must cover each deployed service exactly once",
);

const sbomMatch = workflow.match(/done <<'IMAGES'\s+([\s\S]*?)\s+IMAGES/u);
assert.ok(sbomMatch, "SBOM image inventory is missing");
const sbomImages = sbomMatch[1]
  .trim()
  .split(/\r?\n/u)
  .map((line) => line.trim().split("=").at(1));
assert.deepEqual(
  [...sbomImages].sort(),
  [...expectedImages].sort(),
  "SBOM generation must cover each deployed image exactly once",
);
assert.match(
  normalisedWorkflow,
  /timeout-minutes: 45/u,
  "cold container validation needs a conservative measured deadline",
);
assert.match(
  postgresDockerfile,
  /AS vector-build[\s\S]*?rm -f \/usr\/local\/bin\/gosu[\s\S]*?FROM postgres:/u,
  "the scanned PostgreSQL builder must remove its unused privilege helper",
);

for (const required of [
  "network_mode: none",
  "networks: [data, workflow]",
  "networks: [data, scanner, service, workflow]",
  "networks: [front-door, service]",
  "front-door:",
  "service: {internal: true}",
  "workflow: {internal: true}",
]) {
  assert.ok(compose.includes(required), `Compose security boundary is missing: ${required}`);
}

for (const dockerfile of [
  "apps/api/Dockerfile",
  "apps/web/Dockerfile",
  "infra/clamav/Dockerfile",
  "infra/postgres/Dockerfile",
  "scripts/actionlint.Dockerfile",
  "scripts/secret-scan.Dockerfile",
  "scripts/trufflehog-scan.Dockerfile",
]) {
  const source = await readFile(join(repositoryRoot, dockerfile), "utf8");
  assert.match(
    source,
    /^# syntax=docker\/dockerfile-upstream:master@sha256:[a-f0-9]{64}$/mu,
    `${dockerfile} must pin its external Dockerfile frontend`,
  );
}

const actionlintDockerfile = await readFile(
  join(repositoryRoot, "scripts/actionlint.Dockerfile"),
  "utf8",
);
assert.match(actionlintDockerfile, /FROM golang:1\.26\.6-alpine3\.23@sha256:/u);
assert.match(
  actionlintDockerfile,
  /go install github\.com\/rhysd\/actionlint\/cmd\/actionlint@v1\.7\.12/u,
);
assert.match(actionlintDockerfile, /FROM alpine:3\.23@sha256:/u);

const gitleaksDockerfile = await readFile(
  join(repositoryRoot, "scripts/secret-scan.Dockerfile"),
  "utf8",
);
assert.match(
  gitleaksDockerfile,
  /FROM golang:1\.26\.6-alpine3\.23@sha256:[a-f0-9]{64} AS build/u,
);
assert.match(gitleaksDockerfile, /FROM alpine:3\.23@sha256:[a-f0-9]{64} AS tool/u);
assert.match(gitleaksDockerfile, /zricethezav\/gitleaks\/v8@v8\.30\.1/u);
assert.match(gitleaksDockerfile, /golang\.org\/x\/crypto@v0\.52\.0/u);
assert.match(gitleaksDockerfile, /golang\.org\/x\/text@v0\.39\.0/u);

const webDockerfile = await readFile(join(repositoryRoot, "apps/web/Dockerfile"), "utf8");
assert.match(webDockerfile, /FROM node:24-alpine@sha256:[a-f0-9]{64}/u);
assert.ok(!webDockerfile.includes("node:25"), "apps/web/Dockerfile still uses unsupported Node 25");

const trufflehogDockerfile = await readFile(
  join(repositoryRoot, "scripts/trufflehog-scan.Dockerfile"),
  "utf8",
);
assert.match(trufflehogDockerfile, /FROM alpine:3\.23@sha256:[a-f0-9]{64} AS gate/u);
assert.match(trufflehogDockerfile, /apk add --no-cache nodejs=24\.18\.1-r0/u);
assert.ok(
  !trufflehogDockerfile.includes("FROM node:"),
  "the TruffleHog gate must not carry npm package metadata",
);
for (const required of [
  "trap cleanup EXIT INT TERM",
  "docker network create --internal",
  "--network-alias api",
  "uvicorn.run(app",
  "access_log=False",
  "path_marker=",
  "query_marker=",
  "agent_marker=",
  "docker logs",
  "combined_logs=",
  "grep -F \"$marker\"",
  "Raw request marker leaked into built-container logs",
  "\"event\":\"http_request\"",
  "\"route\":\"unmatched\"",
  "\"status\":404",
]) {
  assert.ok(canary.includes(required), `runtime canary is missing: ${required}`);
}
assert.match(canary, /attempt.*-ge 30/su, "runtime readiness must be bounded");
assert.match(
  canary,
  /for marker in "\$path_marker" "\$query_marker" "\$agent_marker"/u,
  "every injected raw request marker must be checked",
);
assert.match(
  normalisedWorkflow,
  /if: always\(\).*docker compose down .*--volumes --remove-orphans/u,
  "container teardown must run after success, failure or cancellation",
);

console.log("Container workflow contract passed.");
