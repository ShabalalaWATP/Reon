import assert from "node:assert/strict";
import { chmod, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const lineGate = join(scriptDirectory, "check-file-lines.mjs");
const terminologyGate = join(scriptDirectory, "check-terminology.mjs");
const requiredDirectories = [
  ".github",
  "apps/api/src",
  "apps/api/tests",
  "apps/api/alembic",
  "apps/web/src",
  "apps/web/scripts",
  "infra",
  "scripts",
  "workflow",
];

async function createFixture(root) {
  for (const path of requiredDirectories) {
    await mkdir(join(root, path), { recursive: true });
  }
  await mkdir(join(root, "docs"), { recursive: true });
  await writeFile(join(root, ".github/ci.yml"), "name: fixture\n");
  await writeFile(join(root, "apps/api/src/app.py"), "value = 'safe'\n");
  await writeFile(join(root, "apps/api/tests/test_app.py"), "def test_safe():\n    pass\n");
  await writeFile(join(root, "apps/web/src/app.ts"), "export const safe = true;\n");
  await writeFile(join(root, "apps/web/scripts/check.mjs"), "export {};\n");
  await writeFile(
    join(root, "apps/web/src/approved.ts"),
    "export const analyst_queue = 'JIOCAnalyst serviceProduct dissemination disseminate disseminated defence-in-depth from_collection';\n",
  );
  await writeFile(join(root, "infra/check.sh"), "#!/usr/bin/env sh\n");
  await writeFile(join(root, "scripts/check.mjs"), "export {};\n");
  await writeFile(join(root, "workflow/process.bpmn"), "<definitions />\n");
  await writeFile(join(root, "docker-compose.yml"), "services: {}\n");
  await writeFile(join(root, "apps/api/Dockerfile"), "FROM scratch\n");
  await writeFile(join(root, "apps/api/alembic.ini"), "[alembic]\n");
  await writeFile(join(root, "apps/api/alembic/env.py"), "value = 'safe'\n");
  await writeFile(join(root, "apps/api/alembic/script.py.mako"), "safe\n");
  await writeFile(join(root, "apps/api/pyproject.toml"), "[project]\n");
  await writeFile(join(root, "apps/web/Dockerfile"), "FROM scratch\n");
  await writeFile(join(root, "apps/web/eslint.config.js"), "export default {};\n");
  await writeFile(join(root, "apps/web/index.html"), "<main>Safe</main>\n");
  await writeFile(join(root, "apps/web/nginx.conf"), "events {}\n");
  await writeFile(join(root, "apps/web/package.json"), "{}\n");
  await writeFile(join(root, "apps/web/vite.config.ts"), "export default {};\n");
  await writeFile(join(root, "package.json"), "{}\n");
  await writeFile(join(root, "pnpm-workspace.yaml"), "packages: []\n");
}

function run(script, root) {
  return spawnSync(process.execPath, [script], {
    cwd: root,
    encoding: "utf8",
    windowsHide: true,
  });
}

function expectFailure(result, expected) {
  assert.notEqual(result.status, 0, "gate unexpectedly succeeded");
  assert.match(result.stderr, expected);
}

const fixtureRoot = await mkdtemp(join(tmpdir(), "istari-quality-gates-"));
try {
  await createFixture(fixtureRoot);
  assert.equal(run(lineGate, fixtureRoot).status, 0);
  assert.equal(run(terminologyGate, fixtureRoot).status, 0);

  const limitFixture = join(fixtureRoot, "scripts/limit.mjs");
  await writeFile(limitFixture, "safe\n".repeat(350));
  assert.equal(run(lineGate, fixtureRoot).status, 0);
  await writeFile(limitFixture, "safe\n".repeat(351));
  expectFailure(run(lineGate, fixtureRoot), /scripts\/limit\.mjs: 351 lines/u);
  await rm(limitFixture);

  // Documentation is an evidence artefact, not hand-written application source.
  await writeFile(join(fixtureRoot, "docs/long-evidence.md"), "evidence\n".repeat(500));
  assert.equal(run(lineGate, fixtureRoot).status, 0);

  await writeFile(
    join(fixtureRoot, "apps/web/src/legacy.ts"),
    "export const RFIQueue = 'military_queue intelligence disseminated agentRouting chatBot collectionRequest';\n",
  );
  expectFailure(run(terminologyGate, fixtureRoot), /Legacy terminology found/u);
  await rm(join(fixtureRoot, "apps/web/src/legacy.ts"));

  await rm(join(fixtureRoot, "apps/api/src"), { recursive: true });
  expectFailure(run(lineGate, fixtureRoot), /Required root is missing: apps\/api\/src/u);
  expectFailure(
    run(terminologyGate, fixtureRoot),
    /Required root is missing: apps\/api\/src/u,
  );
  await mkdir(join(fixtureRoot, "apps/api/src"));

  await rm(join(fixtureRoot, "workflow"), { recursive: true });
  await writeFile(join(fixtureRoot, "workflow"), "not a directory\n");
  expectFailure(run(lineGate, fixtureRoot), /Required root is not a directory: workflow/u);
  expectFailure(
    run(terminologyGate, fixtureRoot),
    /Required root is not a directory: workflow/u,
  );
  await rm(join(fixtureRoot, "workflow"));
  await mkdir(join(fixtureRoot, "workflow"));

  await rm(join(fixtureRoot, "docker-compose.yml"));
  await mkdir(join(fixtureRoot, "docker-compose.yml"));
  expectFailure(
    run(lineGate, fixtureRoot),
    /Required target is not a file: docker-compose\.yml/u,
  );
  await rm(join(fixtureRoot, "docker-compose.yml"), { recursive: true });
  await writeFile(join(fixtureRoot, "docker-compose.yml"), "services: {}\n");

  if (process.platform !== "win32") {
    const rootPath = join(fixtureRoot, "workflow");
    await chmod(rootPath, 0o000);
    try {
      expectFailure(run(terminologyGate, fixtureRoot), /Cannot read required root tree/u);
    } finally {
      await chmod(rootPath, 0o700);
    }

    const targetPath = join(fixtureRoot, "docker-compose.yml");
    await chmod(targetPath, 0o000);
    try {
      expectFailure(run(lineGate, fixtureRoot), /Cannot read required target/u);
    } finally {
      await chmod(targetPath, 0o600);
    }
  }
} finally {
  await rm(fixtureRoot, { recursive: true, force: true });
}

console.log("Repository quality-gate tests passed.");
