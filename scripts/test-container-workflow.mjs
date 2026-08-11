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
const normalisedWorkflow = workflow.replace(/\s+/gu, " ");
const expectedImages = [
  "istari-service-local-api",
  "istari-service-local-web",
  "istari/postgres-local:17.10-pgvector0.8.1-alpine3.23",
  "istari/camunda-local:8.9.14",
  "istari/clamav-local:1.5.3",
];

for (const required of [
  "push:",
  "pull_request:",
  "schedule:",
  "name: Container and Compose validation",
  "docker compose build api web postgres orchestration clamav",
  "alembic downgrade -1",
  "alembic upgrade head",
  "alembic check",
  "name: Generate CycloneDX image SBOMs",
  "api=istari-service-local-api",
  "web=istari-service-local-web",
  "postgres=istari/postgres-local:17.10-pgvector0.8.1-alpine3.23",
  "camunda=istari/camunda-local:8.9.14",
  "clamav=istari/clamav-local:1.5.3",
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
  normalisedWorkflow,
  /if: always\(\).*docker compose down .*--volumes --remove-orphans/u,
  "container teardown must run after success, failure or cancellation",
);

console.log("Container workflow contract passed.");
